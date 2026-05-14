from fastapi import APIRouter, Header, BackgroundTasks, HTTPException, status, Query
from typing import Optional, List, Dict, Any
import uuid
import hashlib
from datetime import datetime, timezone

from app.core.config import config
from app.models.similarity import SimilarityDetector
from app.models.harm_calculator import HarmCalculator
from app.core import database
from app.core.logging import log_audit
from app.models.pydantic_models import SystemicPatternResponse

router = APIRouter(prefix="/api/v1", tags=["aggregation"])

async def aggregate_similar_cases(
    entity_id: str,
    similarity_threshold: float = config.SIMILARITY_THRESHOLD,
    min_cases: int = config.MIN_CASES_FOR_AGGREGATION,
    description_summary: Optional[str] = None,
    admin_key: Optional[str] = None
) -> Dict[str, Any]:
    async with database.db_pool.acquire() as conn:
        entries = await conn.fetch("""
            SELECT entry_id, description, harm_ly, financial_usd, harm_ecy, num_affected
            FROM entries
            WHERE entity_id = $1 AND status IN ('APPROVED', 'DISPUTED', 'REFUTED')
              AND systemic_key IS NULL
            ORDER BY created_at DESC
        """, entity_id)

        if len(entries) < min_cases:
            return {"message": "Not enough cases for aggregation", "count": len(entries)}

        entries_list = [dict(e) for e in entries]
        clusters = []
        processed = set()

        for i, e1 in enumerate(entries_list):
            if str(e1['entry_id']) in processed:
                continue
            cluster = [str(e1['entry_id'])]
            for e2 in entries_list[i+1:]:
                if str(e2['entry_id']) in processed:
                    continue
                score = SimilarityDetector.similarity_score(e1['description'], e2['description'])
                if score >= similarity_threshold:
                    cluster.append(str(e2['entry_id']))
            if len(cluster) >= min_cases:
                clusters.append({"entry_ids": cluster, "description": e1['description']})
                processed.update(cluster)

        created_patterns = []
        for cluster in clusters:
            pattern_id = str(uuid.uuid4())
            pattern_hash = hashlib.sha256(f"{entity_id}:{cluster['description']}".encode()).hexdigest()[:12]

            harm = await conn.fetchrow("""
                SELECT SUM(harm_ly) as ly, SUM(financial_usd) as usd,
                       SUM(harm_ecy) as ecy, SUM(num_affected) as affected
                FROM entries WHERE entry_id::text = ANY($1)
            """, cluster['entry_ids'])

            await conn.execute("""
                INSERT INTO systemic_patterns (
                    systemic_pattern_id, entity_id, pattern_hash, description,
                    description_summary, similarity_threshold, entry_ids,
                    total_harm_ly, total_financial_usd, total_harm_ecy,
                    total_affected, pattern_confidence, auto_detected
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """,
                pattern_id, entity_id, pattern_hash, cluster['description'][:500],
                description_summary or f"Systemic pattern ({len(cluster['entry_ids'])} cases)",
                similarity_threshold, cluster['entry_ids'],
                float(harm['ly'] or 0), float(harm['usd'] or 0), float(harm['ecy'] or 0),
                int(harm['affected'] or 0),
                HarmCalculator.update_confidence(int(harm['affected'] or 0)),
                admin_key is None
            )

            await conn.executemany(
                "UPDATE entries SET systemic_key = $1 WHERE entry_id::text = $2",
                [(pattern_hash, eid) for eid in cluster['entry_ids']]
            )

            created_patterns.append({
                "systemic_pattern_id": pattern_id,
                "pattern_hash": pattern_hash,
                "entry_count": len(cluster['entry_ids'])
            })

        return {
            "clusters_found": len(clusters),
            "patterns_created": len(created_patterns),
            "patterns": created_patterns
        }

@router.post("/entities/{entity_id}/aggregate")
async def manual_aggregate(
    entity_id: str,
    background_tasks: BackgroundTasks,
    similarity_threshold: float = Query(config.SIMILARITY_THRESHOLD),
    min_cases: int = Query(config.MIN_CASES_FOR_AGGREGATION),
    description_summary: Optional[str] = None,
    x_admin_key: Optional[str] = Header(None)
):
    if config.ENVIRONMENT == "production" and not x_admin_key:
        raise HTTPException(status_code=401, detail="Admin key required")
    background_tasks.add_task(aggregate_similar_cases, entity_id, similarity_threshold, min_cases, description_summary, x_admin_key)
    return {"status": "aggregation_started"}
    
@router.get("/entities/{entity_id}/systemic-patterns")
async def get_systemic_patterns(entity_id: str, limit: int = 20, offset: int = 0) -> List[SystemicPatternResponse]:
    async with database.db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT systemic_pattern_id, entity_id, pattern_hash, description_summary,
                   array_length(entry_ids, 1) as entry_count,
                   total_harm_ly, total_financial_usd, total_harm_ecy,
                   total_affected, pattern_confidence, created_at
            FROM systemic_patterns
            WHERE entity_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """, entity_id, limit, offset)

        return [SystemicPatternResponse(**dict(r)) for r in rows]