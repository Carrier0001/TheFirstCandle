from fastapi import APIRouter, HTTPException, status
from datetime import datetime, timezone
from app.models.evidence_indexer import EvidenceIndexer
from app.core import database

router = APIRouter()

@router.get("/health")
async def health_check():
    try:
        if database.db_pool is None:
            raise Exception("Database pool not initialized")
        async with database.db_pool.acquire() as conn:
            await conn.execute("SELECT 1")
        daily_index = await EvidenceIndexer.get_daily_index()
        return {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": "connected",
            "evidence_today": daily_index["total_files"]
        }
    except Exception as e:
        from app.core.logging import log_audit
        log_audit("HEALTH_CHECK_FAILED", "SYSTEM", "SYSTEM", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unhealthy"
        )

@router.get("/metrics")
async def metrics():
    if database.db_pool is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    async with database.db_pool.acquire() as conn:
        metrics_data = await conn.fetchrow("""
            SELECT 
                (SELECT COUNT(*) FROM submissions) as total_submissions,
                (SELECT COUNT(*) FROM entries) as total_entries,
                (SELECT COUNT(*) FROM systemic_patterns) as total_systemic_patterns,
                (SELECT COUNT(*) FROM evidence_files WHERE pending = FALSE) as total_evidence_files,
                (SELECT COALESCE(SUM(total_size_bytes), 0) FROM evidence_daily_index) as total_evidence_size,
                (SELECT COUNT(*) FROM submissions WHERE status = 'PENDING_JURY') as pending_submissions,
                (SELECT COUNT(*) FROM entries WHERE systemic_key IS NOT NULL) as aggregated_entries
        """)

        daily_evidence = await conn.fetchrow("""
            SELECT * FROM evidence_daily_index 
            WHERE date = CURRENT_DATE
        """)

        return {
            "totals": {
                "submissions": metrics_data['total_submissions'],
                "entries": metrics_data['total_entries'],
                "systemic_patterns": metrics_data['total_systemic_patterns'],
                "evidence_files": metrics_data['total_evidence_files'],
                "evidence_size_gb": round(metrics_data['total_evidence_size'] / (1024**3), 2),
                "pending_submissions": metrics_data['pending_submissions'],
                "aggregated_entries": metrics_data['aggregated_entries']
            },
            "today": dict(daily_evidence) if daily_evidence else {
                "evidence_files": 0, "evidence_size_mb": 0, "unique_submissions": 0
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }