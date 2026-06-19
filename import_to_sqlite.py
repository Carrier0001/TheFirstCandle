# import_to_sqlite.py
import json
import sqlite3
import hashlib
import uuid
from pathlib import Path
from datetime import datetime
import httpx

def get_all_files():
    """Get list of all JSON files from GitHub"""
    api_url = "https://api.github.com/repos/Carrier0001/TheFirstCandle/contents/Data"
    try:
        response = httpx.get(api_url, timeout=30.0)
        response.raise_for_status()
        files = [item["name"] for item in response.json() if item["name"].endswith(".json")]
        return files
    except Exception as e:
        print(f"❌ Error getting file list: {e}")
        return []

def import_to_sqlite():
    """Import directly to SQLite (faster than ledger)"""
    
    db_path = Path("./ledger/ledger.db")
    
    if not db_path.exists():
        print("❌ Database not found. Run the app once first.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    base_url = "https://raw.githubusercontent.com/Carrier0001/TheFirstCandle/main/Data"
    
    # Get all JSON files
    files = get_all_files()
    
    if not files:
        print("❌ No files found")
        return
    
    print(f"📁 Found {len(files)} JSON files")
    
    imported = 0
    skipped = 0
    errors = 0
    
    for filename in files:
        try:
            url = f"{base_url}/{filename}"
            print(f"📥 Processing: {filename}")
            
            response = httpx.get(url, timeout=30.0)
            response.raise_for_status()
            
            data = response.json()
            
            if "entity_id" in data and "entries" in data:
                entity_id = data["entity_id"]
                entity_name = data.get("entity_name", entity_id.replace('_', ' ').title())
                
                file_imported = 0
                for entry in data["entries"]:
                    if (entry.get("harm_ly", 0) == 0 and 
                        entry.get("surplus_ly", 0) == 0 and 
                        not entry.get("description")):
                        skipped += 1
                        continue
                    
                    submission_id = entry.get("entry_id", str(uuid.uuid4()))
                    submission_hash = hashlib.sha256(
                        f"{entity_id}{entry.get('description', '')}{datetime.now()}".encode()
                    ).hexdigest()
                    
                    try:
                        cursor.execute("""
                            INSERT OR REPLACE INTO submissions (
                                submission_id, submission_hash, entity_id, entity_name,
                                title, description, incident_country, incident_year,
                                life_loss, financial_loss, submitter_pubkey_hash, status, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            submission_id,
                            submission_hash,
                            entity_id,
                            entity_name,
                            f"{entity_name} - {entry.get('incident_type', 'Incident')}",
                            entry.get("description", ""),
                            "Global",
                            entry.get("year", 2025),
                            abs(entry.get("harm_ly", 0)),
                            abs(entry.get("harm_ecy", 0)),
                            "github_import",
                            "APPROVED",
                            entry.get("date_logged", datetime.now().isoformat())
                        ))
                        imported += 1
                        file_imported += 1
                    except Exception as e:
                        errors += 1
                        print(f"    ❌ Error importing entry: {e}")
                
                conn.commit()
                print(f"  ✅ Imported {file_imported} entries from {filename}")
            else:
                print(f"  ⚠️ Unknown format in {filename}")
                errors += 1
            
        except Exception as e:
            errors += 1
            print(f"  ❌ Error with {filename}: {e}")
    
    conn.close()
    print(f"\n{'='*50}")
    print(f"📊 IMPORT COMPLETE")
    print(f"{'='*50}")
    print(f"✅ Imported: {imported}")
    print(f"⏭️  Skipped: {skipped}")
    print(f"❌ Errors: {errors}")
    print(f"{'='*50}")

if __name__ == "__main__":
    print("🔄 Importing JSON data into SQLite...")
    print("="*50)
<<<<<<< HEAD
    import_to_sqlite()
=======
    import_to_sqlite()
>>>>>>> ea1a7023d4be0cc3672d28345b42de31c73b0aa9
