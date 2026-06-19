# app/core/database.py - The full distributed ledger
import os
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional
import git
import hashlib
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

logger = logging.getLogger("vow")

class DistributedLedger:
    def __init__(self, data_dir: Path = None):
        # Use persistent disk on Render, local directory elsewhere
        if data_dir is None:
            if os.getenv("RENDER"):
                data_dir = Path("/opt/render/project/src/ledger")
            else:
                data_dir = Path("./ledger")
        
        self.data_dir = data_dir
        self.entities_dir = data_dir / "entities"
        self.submissions_dir = data_dir / "submissions"
        self.db_path = data_dir / "ledger.db"
        
        # Create directories
        for d in [self.entities_dir, self.submissions_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        # Initialize Git repo if it doesn't exist
        if not (data_dir / ".git").exists():
            self.repo = git.Repo.init(data_dir)
        else:
            self.repo = git.Repo(data_dir)
        
        # IPFS is optional - skip if not available
        try:
            import ipfshttpclient
            self.ipfs = ipfshttpclient.connect('/dns/ipfs-daemon/tcp/5001/http')
            logger.info("✅ Connected to IPFS")
        except:
            self.ipfs = None
            logger.info("ℹ️ Running without IPFS (file storage only)")
        
        self._init_sqlite()
        logger.info("✅ DistributedLedger initialized")
    
    def _init_sqlite(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS submissions (
                    submission_id TEXT PRIMARY KEY,
                    submission_hash TEXT UNIQUE NOT NULL,
                    entity_id TEXT NOT NULL,
                    entity_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    incident_country TEXT NOT NULL,
                    incident_year INTEGER NOT NULL,
                    life_loss INTEGER DEFAULT 0,
                    financial_loss REAL DEFAULT 0,
                    submitter_pubkey_hash TEXT NOT NULL,
                    status TEXT DEFAULT 'PENDING_JURY',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entity_id ON submissions(entity_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON submissions(status)")
    
    async def submit_entry(self, entry: Dict) -> Dict:
        entity_file = self.entities_dir / f"{entry['entity_id']}.json"
        
        with open(entity_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
        
        self.repo.index.add([str(entity_file)])
        commit = self.repo.index.commit(f"Entry {entry['submission_id']}")
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO submissions (
                    submission_id, submission_hash, entity_id, entity_name,
                    title, description, incident_country, incident_year,
                    life_loss, financial_loss, submitter_pubkey_hash, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry['submission_id'],
                entry['submission_hash'],
                entry['entity_id'],
                entry['entity_name'],
                entry['title'],
                entry['description'],
                entry['incident_country'],
                entry['incident_year'],
                entry.get('life_loss', 0),
                entry.get('financial_loss', 0.0),
                entry['submitter_pubkey_hash'],
                'PENDING_JURY'
            ))
        
        cid = None
        if self.ipfs:
            try:
                with open(entity_file, 'rb') as f:
                    cid = self.ipfs.add(f, pin=True)['Hash']
            except:
                pass
        
        return {
            "submission_id": entry['submission_id'],
            "git_commit": str(commit),
            "ipfs_cid": cid,
            "status": "PENDING_JURY"
        }
    
    async def get_submissions(self, entity_id: Optional[str] = None) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if entity_id:
                cursor = conn.execute(
                    "SELECT * FROM submissions WHERE entity_id = ? ORDER BY created_at DESC",
                    (entity_id,)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM submissions ORDER BY created_at DESC"
                )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_submission(self, submission_id: str) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM submissions WHERE submission_id = ?",
                (submission_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

# Global instance
_ledger = None

async def init_db():
    global _ledger
    _ledger = DistributedLedger()
    logger.info("🚀 Distributed Ledger initialized")
    return _ledger

async def close_db():
    global _ledger
    if _ledger and _ledger.ipfs:
        try:
            _ledger.ipfs.close()
        except:
            pass
    logger.info("🛑 Distributed Ledger shut down")

def get_ledger():
    return _ledger

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        yield
    finally:
        await close_db()
