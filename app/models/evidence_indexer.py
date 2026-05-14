from typing import List
from datetime import datetime, timezone
from app.core import database

class EvidenceIndexer:
    @staticmethod
    async def index_evidence(submission_id: str, files: List[dict]):
        date = datetime.now(timezone.utc).date()
        total_size = sum(f['size'] for f in files)

        async with database.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO evidence_daily_index (date, total_files, total_size_bytes, unique_submissions)
                VALUES ($1, $2, $3, 1)
                ON CONFLICT (date) DO UPDATE SET
                    total_files = evidence_daily_index.total_files + $2,
                    total_size_bytes = evidence_daily_index.total_size_bytes + $3,
                    unique_submissions = evidence_daily_index.unique_submissions + 1,
                    updated_at = NOW()
            """, date, len(files), total_size)

            for f in files:
                await conn.execute("""
                    INSERT INTO evidence_files (file_hash, submission_id, original_filename, file_size, mime_type, storage_location, pending)
                    VALUES ($1, $2, $3, $4, $5, $6, TRUE)
                    ON CONFLICT (file_hash) DO NOTHING
                """, f['hash'], submission_id, f['filename'], f['size'], f['mime_type'], f['storage_path'])

    @staticmethod
    async def get_daily_index(date=None):
        target = date.date() if date else datetime.now(timezone.utc).date()
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM evidence_daily_index WHERE date = $1", target)
            return dict(row) if row else {"date": str(target), "total_files": 0, "total_size_bytes": 0, "unique_submissions": 0}