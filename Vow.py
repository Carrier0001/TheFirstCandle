from flask import Flask, render_template, request, jsonify
import json
import os
from datetime import datetime
from harm_calculator import LedgerEntry, LedgerCalculator, HarmType, Confidence

app = Flask(__name__)
DATA_FOLDER = "data"

def ensure_data_folder():
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)

@app.route("/")
def index():
    """Home page — show all entities"""
    ensure_data_folder()
    entities = []
    
    for filename in sorted(os.listdir(DATA_FOLDER)):
        if filename.endswith(".json"):
            entity_id = filename.replace(".json", "")
            try:
                with open(os.path.join(DATA_FOLDER, filename), "r") as f:
                    entity = json.load(f)
                    entries = [LedgerEntry(**item) for item in entity.get("entries", [])]
                    if entries:
                        balance = LedgerCalculator.historical_balance(entity_id, entries)
                        entities.append({
                            "id": entity_id,
                            "name": entity_id.replace("_", " ").title(),
                            "entries": len(entries),
                            "outstanding_ly": balance.outstanding_ly,
                            "outstanding_ecy": balance.outstanding_ecy
                        })
            except Exception as e:
                print(f"Error loading {filename}: {e}")
    
    return render_template("index.html", entities=entities)

@app.route("/entity/<entity_id>")
def view_entity(entity_id):
    """View detailed ledger for an entity"""
    filepath = os.path.join(DATA_FOLDER, f"{entity_id}.json")
    
    if not os.path.exists(filepath):
        return "Entity not found", 404
    
    with open(filepath, "r") as f:
        entity = json.load(f)
        entries = [LedgerEntry(**item) for item in entity.get("entries", [])]
    
    # Historical balance
    balance = LedgerCalculator.historical_balance(entity_id, entries)

    # Annual balance (if not ancient)
    years_with_data = sorted(set(e.year for e in entries))
    latest_year = max(years_with_data) if years_with_data else None
    has_negative_year = any(e.year < 0 for e in entries)
    annual = None
    if latest_year and not has_negative_year:
        annual = LedgerCalculator.calculate_annual_view(entity, entries, latest_year)

    # Harm breakdown (with multipliers)
    harm_types = {}
    for entry in entries:
        if entry.harm_ly < 0 or entry.harm_ecy < 0:
            htype = entry.harm_type
            if htype not in harm_types:
                harm_types[htype] = {"ly": 0, "ecy": 0, "count": 0}
            multiplier = entry.intent_multiplier()
            harm_types[htype]["ly"] += entry.harm_ly * multiplier
            harm_types[htype]["ecy"] += entry.harm_ecy * multiplier
            harm_types[htype]["count"] += 1

    # Group entries by harm type (for listing)
    entries_by_type = {}
    for entry in entries:
        htype = entry.harm_type
        if htype not in entries_by_type:
            entries_by_type[htype] = []
        entries_by_type[htype].append(entry)
    
    return render_template(
        "entity.html", 
        entity_id=entity_id.replace("_", " ").title(),
        balance=balance,
        annual=annual,
        entries=entries,
        entries_by_type=entries_by_type,
        harm_types=harm_types
    )

@app.route("/submit", methods=["GET", "POST"])
def submit_entry():
    """Submit a new ledger entry"""
    if request.method == "POST":
        try:
            data = request.get_json()
            
            # Validate required fields
            required = ["entity_id", "description", "year", "harm_ly", "harm_ecy"]
            if not all(k in data for k in required):
                return jsonify({"error": "Missing required fields"}), 400
            
            # Create entry
            entry_id = f"{data['entity_id']}_entry_{datetime.now().timestamp()}"
            new_entry = LedgerEntry(
                entry_id=entry_id,
                entity_id=data["entity_id"],
                date_logged=datetime.now().isoformat(),
                year=int(data["year"]),
                harm_ly=float(data.get("harm_ly", 0)),
                harm_ecy=float(data.get("harm_ecy", 0)),
                surplus_ly=float(data.get("surplus_ly", 0)),
                surplus_ecy=float(data.get("surplus_ecy", 0)),
                description=data["description"],
                harm_type=data.get("harm_type", "NEGLIGENCE"),
                confidence=Confidence[data.get("confidence", "MEDIUM")],
                age_adjustment_note=data.get("age_adjustment_note", "")
            )
            
            # Load existing or create new
            filepath = os.path.join(DATA_FOLDER, f"{data['entity_id']}.json")
            entity = {}
            entries = []
            if os.path.exists(filepath):
                with open(filepath, "r") as f:
                    entity = json.load(f)
                    entries = entity.get("entries", [])
            
            # Add new entry (store as dict for JSON)
            entries.append({
                "entry_id": new_entry.entry_id,
                "entity_id": new_entry.entity_id,
                "date_logged": new_entry.date_logged,
                "year": new_entry.year,
                "harm_ly": new_entry.harm_ly,
                "harm_ecy": new_entry.harm_ecy,
                "surplus_ly": new_entry.surplus_ly,
                "surplus_ecy": new_entry.surplus_ecy,
                "description": new_entry.description,
                "harm_type": new_entry.harm_type,
                "confidence": new_entry.confidence.name,
                "age_adjustment_note": new_entry.age_adjustment_note
            })
            
            # Update entity JSON
            entity["entity_id"] = data["entity_id"]
            entity["entity_state"] = entity.get("entity_state", "ACTIVE")
            entity["entries"] = entries
            
            # Write back
            with open(filepath, "w") as f:
                json.dump(entity, f, indent=2)
            
            return jsonify({"success": True, "entry_id": entry_id})
        
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    return render_template("submit.html", harm_types=[h.name for h in HarmType])

@app.route("/info")
def info():
    return render_template("info.html")
    
    
if __name__ == "__main__":
    ensure_data_folder()
    app.run(debug=True, port=5000)
