import uuid
from app.core import database
from app.core.config import config
from app.models.harm_calculator import HarmCalculator
from app.core.logging import log_audit

async def check_auto_aggregation(entity_id: str):
    async with database.db_pool.acquire() as conn:
        count = await conn.fetchval("""
            SELECT COUNT(*) FROM entries 
            WHERE entity_id = $1 AND systemic_key IS NULL
            AND status IN ('APPROVED', 'DISPUTED', 'REFUTED')
        """, entity_id)

        if count >= config.MIN_CASES_FOR_AGGREGATION * 2:
            from app.api.aggregation import aggregate_similar_cases  # local import to avoid circular
            try:
                result = await aggregate_similar_cases(entity_id)
                log_audit("AUTO_AGGREGATION_TRIGGERED", "SYSTEM", "SYSTEM",
                          entity_id=entity_id, result=result)
            except Exception as e:
                log_audit("AUTO_AGGREGATION_FAILED", "SYSTEM", "SYSTEM", entity_id=entity_id, error=str(e))