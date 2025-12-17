import sqlite3
from datetime import datetime

def create_ledger():
    """Creates the ledger database with all required tables"""
    
    conn = sqlite3.connect('ledger.db')
    c = conn.cursor()
    
    print("Creating ledger database...")
    
    # Main ledger table (all entries)
    c.execute('''
        CREATE TABLE IF NOT EXISTS ledger (
            entry_id TEXT PRIMARY KEY,
            date_logged TEXT NOT NULL,
            category TEXT,
            type TEXT,
            intent TEXT,
            description TEXT,
            harm_cost_ly REAL DEFAULT 0,
            harm_cost_ecy REAL DEFAULT 0,
            surplus_ly REAL DEFAULT 0,
            surplus_ecy REAL DEFAULT 0,
            irreversible_debt_ly REAL DEFAULT 0,
            irreversible_debt_ecy REAL DEFAULT 0,
            source TEXT,
            validator_status TEXT DEFAULT 'Pending',
            net_balance REAL,
            patch_status TEXT,
            notes TEXT,
            signature TEXT NOT NULL,
            carrier_pubkey TEXT NOT NULL,
            timestamp INTEGER NOT NULL
        )
    ''')
    print("✓ Created 'ledger' table")
    
    # Carrier keys table (who can sign entries)
    c.execute('''
        CREATE TABLE IF NOT EXISTS carriers (
            pubkey TEXT PRIMARY KEY,
            carrier_name TEXT,
            date_joined TEXT,
            status TEXT DEFAULT 'Active',
            tier TEXT DEFAULT 'Full'
        )
    ''')
    print("✓ Created 'carriers' table")
    
    # Hash chain table (daily Merkle roots for tamper detection)
    c.execute('''
        CREATE TABLE IF NOT EXISTS hash_chain (
            day_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            merkle_root TEXT NOT NULL,
            entries_count INTEGER,
            previous_hash TEXT
        )
    ''')
    print("✓ Created 'hash_chain' table")
    
    # Episodes table (tracks which episode each entry belongs to)
    c.execute('''
        CREATE TABLE IF NOT EXISTS episodes (
            episode_id TEXT PRIMARY KEY,
            episode_number INTEGER,
            title TEXT,
            upload_date TEXT,
            institution TEXT,
            status TEXT DEFAULT 'Published'
        )
    ''')
    print("✓ Created 'episodes' table")
    
    conn.commit()

    
    print("\n✓ Ledger database created successfully: ledger.db")
    print(f"  Location: {conn.total_changes} tables created")
    print(f"  Created at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    conn.close()

if __name__ == "__main__":
    create_ledger()