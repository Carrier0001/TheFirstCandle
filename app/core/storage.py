import json
import sqlite3
from pathlib import Path
import git
import ipfshttpclient
from typing import List, Dict
import hashlib

class DistributedLedger:
    """
    Replaces PostgreSQL with:
    - SQLite for queries (fast, portable)
    - Git for history (immutable, forkable)
    - IPFS for distribution (content-addressed)
    """
    
    def __init__(self, data_dir: Path = Path("./ledger")):
        self.data_dir = data_dir
        self.entities_dir = data_dir / "entities"
        self.submissions_dir = data_dir / "submissions"
        self.db_path = data_dir / "ledger.db"
        
        # Create directories
        for d in [self.entities_dir, self.submissions_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        # Initialize Git repo
        self.repo = git.Repo.init(data_dir)
        
        # Initialize IPFS (local node or remote)
        self.ipfs = ipfshttpclient.connect('/dns/ipfs-daemon/tcp/5001/http')
        
        # Initialize SQLite
        self._init_sqlite()
    
    def _init_sqlite(self):
        """Same schema but local only"""
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
            # No IP storage at all
    
    async def submit_entry(self, entry: Dict) -> Dict:
        """Store entry in JSON, Git commit, IPFS pin"""
        
        # 1. Save as JSON (source of truth)
        entity_file = self.entities_dir / f"{entry['entity_id']}.json"
        
        with open(entity_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
        
        # 2. Git commit (immutable history)
        self.repo.index.add([str(entity_file)])
        commit = self.repo.index.commit(f"Entry {entry['submission_id']}")
        
        # 3. Add to SQLite (for fast queries)
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
        
        # 4. Pin to IPFS (distributed)
        with open(entity_file, 'rb') as f:
            cid = self.ipfs.add(f, pin=True)['Hash']
        
        # 5. Return receipt (no server dependency)
        return {
            "submission_id": entry['submission_id'],
            "git_commit": str(commit),
            "ipfs_cid": cid,
            "verify_url": f"ipfs://{cid}/entities/{entry['entity_id']}.json",
            "status": "PENDING_JURY"
        }
