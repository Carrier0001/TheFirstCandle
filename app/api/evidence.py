from fastapi import APIRouter, Query
from typing import Optional, List, Dict
from datetime import datetime
from app.models.evidence_indexer import EvidenceIndexer
from app.core import database

router = APIRouter(prefix="/api/v1", tags=["evidence"])

@router.get("/evidence/daily-index")
async def daily_index(date: Optional[str] = None, limit: int = 30):
    if date:
        target = datetime.fromisoformat(date).date()
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM evidence_daily_index WHERE date = $1", target)
            return [dict(row)] if row else []
    else:
        async with database.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM evidence_daily_index ORDER BY date DESC LIMIT $1
            """, limit)
            return [dict(r) for r in rows]

@router.get("/evidence/submission/{submission_id}")
async def submission_evidence(submission_id: str):
    async with database.db_pool.acquire() as conn:
        files = await conn.fetch("""
            SELECT file_hash, original_filename, file_size, mime_type, indexed_at, pending
            FROM evidence_files WHERE submission_id = $1
        """, submission_id)
        return {
            "submission_id": submission_id,
            "evidence_files": [dict(f) for f in files],
            "total_files": len(files)
        }