from fastapi import APIRouter, Header, HTTPException, status
import uuid
from app.models.enums import HarmType
from app.models.harm_calculator import HarmCalculator
from app.core.config import config
from app.core import database
from app.core.logging import log_audit
from app.utils.background import check_auto_aggregation

router = APIRouter(prefix="/api/v1", tags=["admin"])

@router.post("/admin/quick-approve/{submission_id}")
async def quick_approve(
    submission_id: str,
    x_admin_key: str = Header(...),
    intent_type: str = "NEGLIGENCE"
):
    if config.ENVIRONMENT == "production" and not x_admin_key:
        raise HTTPException(status_code=401, detail="Admin key required")

    try:
        intent = HarmType[intent_type.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid intent_type. Must be one of: {', '.join([h.name for h in HarmType])}")

    async with database.db_pool.acquire() as conn:
        async with conn.transaction():
            sub = await conn.fetchrow("""
                SELECT * FROM submissions WHERE submission_id = $1 AND status = 'PENDING_JURY'
            """, submission_id)
            
            if not sub:
                raise HTTPException(status_code=404, detail="Submission not found or already processed")

            harm = HarmCalculator.calculate_harm(
                life_loss=sub['life_loss_submitted'] or 0,
                financial_loss=sub['financial_loss_submitted'] or 0.0,
                ecosystem_loss=0.0,
                num_affected=sub['num_victims_submitted'] or 0,
                victim_ages=[None] * (sub['num_victims_submitted'] or 0),
                intent_type=intent
            )

            entry_id = str(uuid.uuid4())
            await conn.execute("""
                INSERT INTO entries (
                    entry_id, entity_id, title, description, status,
                    submitter_pubkey_hash, intent_type, intent_multiplier,
                    num_affected, harm_ly, financial_usd, harm_ecy,
                    confidence, jury_consensus_votes, jury_total_votes, created_at
                ) VALUES ($1, $2, $3, $4, 'APPROVED', $5, $6, $7, $8, $9, $10, $11, $12, 1, 1, NOW())
            """, entry_id, sub['entity_id'], sub['title'], sub['description'],
                sub['submitter_pubkey_hash'], intent.value, harm['intent_multiplier'],
                sub['num_victims_submitted'] or 0, harm['harm_ly'], harm['financial_usd'], harm['harm_ecy'],
                HarmCalculator.update_confidence(sub['num_victims_submitted'] or 0))

            await conn.execute("""
                UPDATE submissions SET status = 'APPROVED', resulting_entry_id = $1, jury_complete_at = NOW()
                WHERE submission_id = $2
            """, entry_id, submission_id)

            await conn.execute("UPDATE evidence_files SET pending = FALSE WHERE submission_id = $1", submission_id)

            log_audit("ADMIN_QUICK_APPROVE", "ADMIN", "SYSTEM", submission_id=submission_id, entity_id=sub['entity_id'], entry_id=entry_id)

    # Trigger aggregation AFTER transaction commits
    await check_auto_aggregation(sub['entity_id'])

    return {"status": "approved", "entry_id": entry_id, "submission_id": submission_id}


@router.get("/admin/pending-submissions")
async def list_pending(x_admin_key: str = Header(...), limit: int = 50, offset: int = 0):
    """Admin endpoint to see what needs review"""
    if config.ENVIRONMENT == "production" and not x_admin_key:
        raise HTTPException(status_code=401, detail="Admin key required")
    
    async with database.db_pool.acquire() as conn:
        submissions = await conn.fetch("""
            SELECT submission_id, entity_id, entity_name, title, description,
                   life_loss_submitted, financial_loss_submitted, num_victims_submitted,
                   incident_country, incident_year, received_at,
                   (SELECT COUNT(*) FROM evidence_files WHERE submission_id = submissions.submission_id) as evidence_count
            FROM submissions
            WHERE status = 'PENDING_JURY'
            ORDER BY received_at DESC
            LIMIT $1 OFFSET $2
        """, limit, offset)
        
        total = await conn.fetchval("SELECT COUNT(*) FROM submissions WHERE status = 'PENDING_JURY'")
        
        return {
            "pending": [dict(s) for s in submissions],
            "total": total,
            "pagination": {"limit": limit, "offset": offset}
        }