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

DATA_FOLDER = "data"
EVIDENCE_FOLDER = "evidence"

MAX_FILE_SIZE_MB = 25
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".txt", ".mp4", ".mp3", ".webm"}


# ------------------------
# Utility helpers
# ------------------------

def ensure_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)


def allowed_file(filename):
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS


# ------------------------
# Entity loading & calculation
# ------------------------

def load_entity_from_file(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        raw = json.load(f)

    entries = []
    for item in raw.get("entries", []):
        try:
            entries.append(LedgerEntry(**item))
        except Exception as e:
            print(f"Error parsing entry in {filepath}: {e}")

    calculator = LedgerCalculator()

    lifetime = calculator.calculate_lifetime_view(entries)
    current_year = max((e.year for e in entries), default=datetime.now().year)
    annual = calculator.calculate_annual_view(entries, current_year)

    raw_breakdown = calculator.harm_breakdown(entries)
    harm_breakdown = dict(
        sorted(
            raw_breakdown.items(),
            key=lambda kv: kv[1]["ly"],
            reverse=True
        )
    )

    return {
        "entity_id": raw["entity_id"],
        "entity_name": raw.get("entity_name", raw["entity_id"].replace("_", " ").title()),
        "entity_state": raw.get("entity_state", "ACTIVE"),
        "measurement_date": raw.get("measurement_date", datetime.now().strftime("%Y-%m-%d")),
        "entries": entries,
        "lifetime": lifetime,
        "current_year": annual,
        "harm_breakdown": harm_breakdown
    }


# ------------------------
# Routes
# ------------------------

@app.route("/")
def index():
    ensure_folder(DATA_FOLDER)

    entities = []
    for filename in sorted(os.listdir(DATA_FOLDER)):
        if filename.endswith(".json"):
            try:
                entities.append(load_entity_from_file(os.path.join(DATA_FOLDER, filename)))
            except Exception as e:
                print(f"Failed to load {filename}: {e}")

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
        abort(404)

    try:
        entity = load_entity_from_file(filepath)
        entries_by_type = defaultdict(list)
        for entry in entity["entries"]:
            entries_by_type[entry.harm_type].append(entry)

        return render_template(
            "entity.html",
            entity=entity,
            entries_by_type=dict(entries_by_type)
        )
    except Exception as e:
        print(f"Error rendering entity {entity_id}: {e}")
        abort(500)


# ------------------------
# SUBMIT (Option B – hardened multipart)
# ------------------------

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

        entity_id = form.get("entity_id", "").strip().lower().replace(" ", "_")
        description = form.get("description", "").strip()
        year = form.get("year")

        if not entity_id or not description or not year:
            return jsonify({"error": "Missing required fields"}), 400

        year = int(year)
        entry_type = form.get("entry_type", "harm")
        confidence = Confidence[form.get("confidence", "MEDIUM")]

        harm_ly = 0
        surplus_ly = 0

        if entry_type == "harm":
            harm_ly = -abs(float(form.get("harm_ly", 0)))
        else:
            surplus_ly = abs(float(form.get("surplus_ly", 0)))

        ensure_folder(EVIDENCE_FOLDER)
        entity_evidence_dir = os.path.join(EVIDENCE_FOLDER, entity_id)
        ensure_folder(entity_evidence_dir)

        evidence_hashes = []
        total_size = 0

        for file in files:
            if not file.filename:
                continue

            filename = secure_filename(file.filename)
            if not allowed_file(filename):
                return jsonify({"error": f"File type not allowed: {filename}"}), 400

            file_bytes = file.read()
            size_mb = len(file_bytes) / (1024 * 1024)
            total_size += size_mb

            if size_mb > MAX_FILE_SIZE_MB:
                return jsonify({"error": f"File too large: {filename}"}), 400

            sha256 = hashlib.sha256(file_bytes).hexdigest()
            evidence_hashes.append(sha256)

            with open(os.path.join(entity_evidence_dir, sha256), "wb") as f:
                f.write(file_bytes)

        if not evidence_hashes and not form.get("evidence_links"):
            return jsonify({"error": "Evidence required"}), 400

        entry = LedgerEntry(
            entry_id=f"{entity_id}_{uuid.uuid4().hex[:12]}",
            entity_id=entity_id,
            date_logged=datetime.now().isoformat(),
            year=year,
            harm_ly=harm_ly,
            harm_ecy=0,
            surplus_ly=surplus_ly,
            surplus_ecy=0,
            description=description[:1000],
            harm_type=form.get("harm_type", "NEGLIGENCE"),
            incident_type=form.get("incident_type", "NEGLIGENCE"),
            confidence=confidence,
            causation_evidence=form.get("evidence_links", ""),
            num_affected=int(form.get("num_affected", 0)),
            avg_age_at_harm=int(form.get("avg_age_at_harm", 0)),
            source_hash=",".join(evidence_hashes),
            response_to_entry_id=""
        )

        filepath = os.path.join(DATA_FOLDER, f"{entity_id}.json")

        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                entity_data = json.load(f)
        else:
            entity_data = {
                "entity_id": entity_id,
                "entity_name": entity_id.replace("_", " ").title(),
                "entity_state": "PENDING_VALIDATION",
                "entries": []
            }

        entity_data["entries"].append(entry.__dict__)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(entity_data, f, indent=2)

        return jsonify({
            "success": True,
            "entity_id": entity_id,
            "entry_id": entry.entry_id
        })

    except Exception as e:
        print("SUBMISSION ERROR:", e)
        return jsonify({"error": "Submission failed"}), 500


# ------------------------
# Static informational pages
# ------------------------

@app.route("/info")
def info():
    return render_template("info.html")


@app.route("/methodology")
def methodology():
    return render_template("methodology.html")


# ------------------------
# Main
# ------------------------

if __name__ == "__main__":
    ensure_folder(DATA_FOLDER)
    ensure_folder(EVIDENCE_FOLDER)
    app.run(debug=True, port=5000)
