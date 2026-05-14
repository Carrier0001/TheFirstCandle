from fastapi import APIRouter, Query, HTTPException, status
from typing import Dict, List, Optional
from app.models.harm_calculator import HarmCalculator
from app.core import database

router = APIRouter(prefix="/api/v1", tags=["entities"])

@router.get("/entities/{entity_id}")
async def get_entity_detail(entity_id: str, include_systemic: bool = True):
    async with database.db_pool.acquire() as conn:
        entity = await conn.fetchrow("""
            SELECT entity_id, MAX(entity_name) as entity_name
            FROM entries WHERE entity_id = $1 GROUP BY entity_id
        """, entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        totals = await conn.fetchrow("""
            SELECT COUNT(*) as total_entries,
                   COUNT(CASE WHEN systemic_key IS NULL THEN 1 END) as individual,
                   SUM(harm_ly) as harm_ly, SUM(financial_usd) as financial_usd,
                   SUM(harm_ecy) as harm_ecy, SUM(num_affected) as affected
            FROM entries WHERE entity_id = $1 AND status IN ('APPROVED','DISPUTED','REFUTED')
        """, entity_id)

        result = {
            "entity_id": entity_id,
            "entity_name": entity['entity_name'],
            "totals": {
                "total_entries": totals['total_entries'],
                "individual_entries": totals['individual'],
                "total_harm_ly": float(totals['harm_ly'] or 0),
                "total_financial_usd": float(totals['financial_usd'] or 0),
                "total_harm_ecy": float(totals['harm_ecy'] or 0),
                "total_affected": int(totals['affected'] or 0)
            },
            "confidence": HarmCalculator.update_confidence(int(totals['affected'] or 0))
        }

        if include_systemic:
            patterns = await conn.fetch("""
                SELECT pattern_hash, description_summary, array_length(entry_ids,1) as count,
                       total_harm_ly, created_at
                FROM systemic_patterns WHERE entity_id = $1 ORDER BY total_harm_ly DESC LIMIT 5
            """, entity_id)
            result["systemic_patterns"] = [dict(p) for p in patterns]

        return result

@router.get("/entities")
async def list_entities(
    sort_by: str = Query("harm", regex="^(harm|entries|recent)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    order_map = {"harm": "total_harm_ly DESC", "entries": "total_entries DESC", "recent": "last_entry DESC"}
    async with database.db_pool.acquire() as conn:
        entities = await conn.fetch(f"""
            SELECT entity_id, MAX(entity_name) as entity_name,
                   COUNT(*) as total_entries,
                   SUM(harm_ly) as total_harm_ly,
                   SUM(num_affected) as total_affected,
                   MAX(created_at) as last_entry
            FROM entries
            WHERE status IN ('APPROVED','DISPUTED','REFUTED')
            GROUP BY entity_id
            ORDER BY {order_map.get(sort_by, "total_harm_ly DESC")}
            LIMIT $1 OFFSET $2
        """, limit, offset)

        total = await conn.fetchval("SELECT COUNT(DISTINCT entity_id) FROM entries")

        return {
            "entities": [
                {
                    "entity_id": e['entity_id'],
                    "entity_name": e['entity_name'],
                    "total_entries": e['total_entries'],
                    "total_harm_ly": float(e['total_harm_ly'] or 0),
                    "total_affected": int(e['total_affected'] or 0),
                    "last_entry": e['last_entry'],
                    "confidence": HarmCalculator.update_confidence(int(e['total_affected'] or 0))
                } for e in entities
            ],
            "pagination": {"limit": limit, "offset": offset, "total": total}
        }