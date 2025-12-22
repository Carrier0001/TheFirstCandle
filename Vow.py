from flask import Flask, render_template, request, jsonify, abort
import os
import json
import uuid
import hashlib
from datetime import datetime
from collections import defaultdict
from werkzeug.utils import secure_filename

from harm_calculator import (
    LedgerEntry,
    LedgerCalculator,
    Confidence,
    HarmType
)

app = Flask(__name__)

# ------------------------
# Paths — works locally and on Render
# ------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(BASE_DIR, "Data")
EVIDENCE_FOLDER = os.path.join(BASE_DIR, "Evidence")

MAX_FILE_SIZE_MB = 25
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".txt", ".mp4", ".mp3", ".webm"}

# ------------------------
# Utility helpers
# ------------------------
def ensure_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"Created folder: {path}")

def allowed_file(filename):
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

# Ensure folders exist on startup
ensure_folder(DATA_FOLDER)
ensure_folder(EVIDENCE_FOLDER)

# ------------------------
# Entity loading
# ------------------------
def load_entity_from_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)

        entries = []
        for item in raw.get("entries", []):
            try:
                entries.append(LedgerEntry(**item))
            except Exception as e:
                print(f"Invalid entry in {filepath}: {e}")

        calculator = LedgerCalculator()
        lifetime = calculator.calculate_lifetime_view(entries)

        # Annual view (only if not ancient)
        years = [e.year for e in entries]
        current_year = max(years) if years else datetime.now().year
        has_ancient = any(y < 0 for y in years)
        annual = calculator.calculate_annual_view(entries, current_year) if not has_ancient else None

        harm_breakdown = dict(sorted(
            calculator.harm_breakdown(entries).items(),
            key=lambda x: x[1]["ly"],
            reverse=True
        ))

        return {
            "entity_id": raw["entity_id"],
            "entity_name": raw.get("entity_name", raw["entity_id"].replace("_", " ").title()),
            "entity_state": raw.get("entity_state", "ACTIVE"),
            "measurement_date": raw.get("measurement_date", datetime.now().strftime("%Y-%m-%d")),
            "entries": entries,
            "lifetime": lifetime,
            "annual": annual,
            "harm_breakdown": harm_breakdown
        }
    except Exception as e:
        print(f"Failed to load entity {filepath}: {e}")
        return None

# ------------------------
# Routes
# ------------------------
@app.route("/")
def index():
    entities = []
    if os.path.exists(DATA_FOLDER):
        for filename in sorted(os.listdir(DATA_FOLDER)):
            if filename.endswith(".json"):
                filepath = os.path.join(DATA_FOLDER, filename)
                entity = load_entity_from_file(filepath)
                if entity:
                    entities.append(entity)

    # Sort by outstanding debt (most negative first)
    entities.sort(key=lambda e: e["lifetime"].outstanding_ly)

    return render_template(
        "index.html",
        entities=entities,
        current_date=datetime.now().strftime("%B %d, %Y")
    )

@app.route("/entity/<entity_id>")
def view_entity(entity_id):
    filepath = os.path.join(DATA_FOLDER, f"{entity_id}.json")
    if not os.path.exists(filepath):
        abort(404, description="Entity not found")

    entity = load_entity_from_file(filepath)
    if not entity:
        abort(500, description="Error loading entity data")

    entries_by_type = defaultdict(list)
    for entry in entity["entries"]:
        entries_by_type[entry.harm_type].append(entry)

    return render_template(
        "entity.html",
        entity=entity,
        entries_by_type=dict(entries_by_type)
    )

@app.route("/submit", methods=["GET", "POST"])
def submit_entry():
    if request.method == "GET":
        return render_template(
            "submit.html",
            harm_types=[ht.name for ht in HarmType]
        )

    try:
        form = request.form
        files = request.files.getlist("evidence_files")

        raw_entity = form.get("entity_id", "").strip()
        if not raw_entity:
            return jsonify({"error": "Entity name required"}), 400

        entity_id = raw_entity.lower().replace(" ", "_").replace("-", "_")
        description = form.get("description", "").strip()
        year_str = form.get("year", "").strip()

        if not description or not year_str:
            return jsonify({"error": "Description and year required"}), 400

        year = int(year_str)
        harm_ly = float(form.get("harm_ly", 0))
        surplus_ly = float(form.get("surplus_ly", 0))

        # Evidence handling
        evidence_hashes = []
        entity_evidence_dir = os.path.join(EVIDENCE_FOLDER, entity_id)
        ensure_folder(entity_evidence_dir)

        for file in files:
            if file and file.filename:
                if not allowed_file(file.filename):
                    return jsonify({"error": f"Disallowed file type: {file.filename}"}), 400

                file_bytes = file.read()
                if len(file_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
                    return jsonify({"error": f"File too large: {file.filename}"}), 400

                file_hash = hashlib.sha256(file_bytes).hexdigest()
                evidence_hashes.append(file_hash)

                save_path = os.path.join(entity_evidence_dir, f"{uuid.uuid4().hex[:8]}_{file_hash}")
                with open(save_path, "wb") as f:
                    f.write(file_bytes)

        if not evidence_hashes and not form.get("evidence_links"):
            return jsonify({"error": "At least one evidence file or link required"}), 400

        # Create entry
        entry = LedgerEntry(
            entry_id=str(uuid.uuid4()),
            entity_id=entity_id,
            date_logged=datetime.now().isoformat(),
            year=year,
            harm_ly=-abs(harm_ly) if harm_ly else 0,
            harm_ecy=0,
            surplus_ly=abs(surplus_ly),
            surplus_ecy=0,
            description=description,
            harm_type=form.get("harm_type", "NEGLIGENCE"),
            confidence=Confidence[form.get("confidence", "MEDIUM")],
            source_hash=",".join(evidence_hashes),
            evidence_links=form.get("evidence_links", "")
        )

        # Load or create entity file
        filepath = os.path.join(DATA_FOLDER, f"{entity_id}.json")
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                entity_data = json.load(f)
        else:
            entity_data = {
                "entity_id": entity_id,
                "entity_name": raw_entity.title(),
                "entity_state": "PENDING_VALIDATION",
                "measurement_date": datetime.now().strftime("%Y-%m-%d"),
                "entries": []
            }

        entity_data["entries"].append(entry.__dict__)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(entity_data, f, indent=2)

        return jsonify({
            "success": True,
            "message": "Entry submitted. Pending validation.",
            "entity_id": entity_id,
            "entry_id": entry.entry_id
        })

    except Exception as e:
        print("SUBMISSION ERROR:", str(e))
        return jsonify({"error": "Server error during submission"}), 500

@app.route("/info")
def info():
    return render_template("info.html")

@app.route("/methodology")
def methodology():
    return render_template("methodology.html")

if __name__ == "__main__":
    app.run(debug=True, port=5000)

