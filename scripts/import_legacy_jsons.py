#!/usr/bin/env python3
import asyncio
import json
import sys
import os
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import asyncpg
    HAS_DB = True
except ImportError:
    HAS_DB = False
    print("⚠️  asyncpg not installed. Run: python -m pip install asyncpg")

async def import_legacy_jsons():
    data_dir = Path(__file__).parent.parent / "Data"
    
    if not data_dir.exists():
        print(f"❌ Data directory not found: {data_dir}")
        return
    
    json_files = list(data_dir.glob("*.json"))
    
    if not json_files:
        print(f"⚠️  No JSON files found in {data_dir}")
        return
    
    print(f"📁 Found {len(json_files)} JSON files in {data_dir}")
    
    if not HAS_DB:
        print("\n❌ Cannot import — missing asyncpg module.")
        print("   Run: python -m pip install asyncpg")
        return
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("\n❌ DATABASE_URL environment variable not set")
        print("   Run: set DATABASE_URL=postgresql://postgres:your_password@localhost:5432/thefirstcandle")
        return
    
    print(f"\n✅ Connecting to database...")
    
    try:
        conn = await asyncpg.connect(database_url)
        print("✅ Connected to PostgreSQL\n")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return
    
    imported = 0
    skipped = 0
    
    for json_path in json_files:
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            entity_name = data.get("entity_name", json_path.stem.replace('_', ' ').title())
            entity_id = data.get("entity_id", json_path.stem)
            
            entries = data.get("entries", [data])
            
            for entry in entries:
                if entry.get("harm_ly") == 0 and entry.get("surplus_ly") == 0 and not entry.get("description"):
                    continue
                
                # Check for duplicate
                desc_preview = entry.get("description", entry.get("title", ""))[:100]
                existing = await conn.fetchval(
                    "SELECT 1 FROM submissions WHERE entity_id = $1 AND incident_year = $2 AND description LIKE $3",
                    entity_id, entry.get("year", 0), f"%{desc_preview[:50]}%"
                )
                if existing:
                    skipped += 1
                    continue
                
                harm_ly = abs(entry.get("harm_ly", 0))
                surplus_ly = entry.get("surplus_ly", 0)
                
                # Generate unique hash for this submission
                unique_string = f"{entity_id}_{entry.get('year', 0)}_{entry.get('description', '')[:100]}"
                submission_hash = hashlib.sha256(unique_string.encode()).hexdigest()
                
                await conn.execute("""
                    INSERT INTO submissions (
                        submission_id, submission_hash, entity_id, entity_name, title, description,
                        incident_year, life_loss_submitted, surplus_ly,
                        financial_loss_submitted, num_victims_submitted,
                        intent_type, confidence, status, evidence_links,
                        source_type, received_at
                    ) VALUES (
                        gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, 'APPROVED', $13, 'legacy_json', NOW()
                    )
                """,
                    submission_hash,
                    entity_id,
                    entity_name,
                    entry.get("title", entry.get("description", "Untitled")[:200]),
                    entry.get("description", ""),
                    entry.get("year", 0),
                    harm_ly,
                    surplus_ly,
                    entry.get("harm_ecy", 0),
                    entry.get("num_affected", 0),
                    entry.get("harm_type", "NEGLIGENCE"),
                    entry.get("confidence", "MEDIUM"),
                    entry.get("causation_evidence", "")
                )
                imported += 1
                print(f"  ✅ {entity_name} ({entry.get('year', '?')})")
                
        except Exception as e:
            print(f"❌ Error in {json_path.name}: {e}")
    
    await conn.close()
    print(f"\n📊 Summary: {imported} imported, {skipped} skipped, {len(json_files)} files processed")

if __name__ == "__main__":
    asyncio.run(import_legacy_jsons())