import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.core.database import lifespan, get_ledger
from app.api import health, submissions, entities, aggregation, evidence, jury, admin
from datetime import datetime
import json
import hashlib
import uuid
import httpx
from pathlib import Path

os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)

app = FastAPI(
    title="The Vow Ledger v1.0",
    description="Permanent truth ledger with jury consensus and smart aggregation",
    version="1.0.0",
    lifespan=lifespan
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# ==================== RAW JINJA2 (NO STARLETTE CACHE) ====================
jinja_env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape(["html", "xml"]),
    cache_size=0,
    auto_reload=True
)
jinja_env.filters['comma_format'] = lambda x: f"{int(x):,}" if x else "0"

def render(template_name: str, request: Request, **context):
    template = jinja_env.get_template(template_name)
    context["request"] = request
    return HTMLResponse(template.render(**context))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if os.getenv("ENVIRONMENT", "development") != "production" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper to check if ledger is ready
def is_ledger_ready():
    ledger = get_ledger()
    return ledger is not None

app.include_router(health.router)
app.include_router(submissions.router)
app.include_router(entities.router)
app.include_router(aggregation.router)
app.include_router(evidence.router)
app.include_router(jury.router)
app.include_router(admin.router)

# ==================== PREVIEW IMPORT (DRY RUN, NO WRITES) ====================
@app.get("/admin/import-preview")
async def import_preview():
    """
    Dry run: fetch everything from GitHub, diff it against what's already
    in the DB, and report what WOULD happen. Does not write anything —
    no file writes, no git commits, no SQLite inserts. Use this to sanity
    check the pipeline before calling /admin/import-data for real.
    """
    try:
        ledger = get_ledger()
        if not ledger:
            return JSONResponse(status_code=503, content={"error": "Ledger not ready"})

        headers = {
            "User-Agent": "VowLedger-App/1.0",
            "Accept": "application/vnd.github.v3+json"
        }
        api_url = "https://api.github.com/repos/Carrier0001/TheFirstCandle/contents/Data"

        existing_ids = await ledger.get_existing_submission_ids()

        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, timeout=30.0, headers=headers)
            if response.status_code != 200:
                return JSONResponse(
                    status_code=response.status_code,
                    content={"error": f"GitHub API error: {response.status_code}"}
                )

            files_data = response.json()
            json_files = [f["name"] for f in files_data if f["name"].endswith(".json")]

            to_add = []
            already_exists = []
            skipped_empty = []
            file_errors = []

            for filename in json_files:
                try:
                    raw_url = f"https://raw.githubusercontent.com/Carrier0001/TheFirstCandle/main/Data/{filename}"
                    file_response = await client.get(raw_url, timeout=30.0, headers=headers)
                    if file_response.status_code != 200:
                        file_errors.append({"file": filename, "reason": f"HTTP {file_response.status_code}"})
                        continue

                    data = file_response.json()
                    if "entity_id" not in data or "entries" not in data:
                        file_errors.append({"file": filename, "reason": "missing entity_id/entries"})
                        continue

                    entity_id = data["entity_id"]
                    entity_name = data.get("entity_name", entity_id.replace('_', ' ').title())

                    for entry in data["entries"]:
                        entry_id = entry.get("entry_id")

                        if (entry.get("harm_ly", 0) == 0 and
                            entry.get("surplus_ly", 0) == 0 and
                            not entry.get("description")):
                            skipped_empty.append(entry_id)
                            continue

                        if entry_id and entry_id in existing_ids:
                            already_exists.append(entry_id)
                        else:
                            to_add.append({
                                "entry_id": entry_id,
                                "entity_id": entity_id,
                                "entity_name": entity_name,
                                "year": entry.get("year"),
                                "description_preview": (entry.get("description", "") or "")[:120]
                            })

                except Exception as e:
                    file_errors.append({"file": filename, "reason": str(e)})

        return JSONResponse(content={
            "files_checked": len(json_files),
            "would_add": len(to_add),
            "already_in_db": len(already_exists),
            "skipped_empty": len(skipped_empty),
            "file_errors": len(file_errors),
            "to_add": to_add,
            "already_in_db_ids": already_exists,
            "file_error_details": file_errors
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# ==================== IMPORT DATA FROM GITHUB ====================
@app.get("/admin/import-data")
async def import_data_from_github():
    """Import all JSON data from GitHub into the ledger"""
    try:
        ledger = get_ledger()
        
        if not ledger:
            return JSONResponse(
                status_code=503,
                content={"error": "Ledger not ready"}
            )
        
        # GitHub API headers to avoid rate limiting
        headers = {
            "User-Agent": "VowLedger-App/1.0",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # GitHub API to get all JSON files
        api_url = "https://api.github.com/repos/Carrier0001/TheFirstCandle/contents/Data"
        
        async with httpx.AsyncClient() as client:
            # Get list of files with proper headers
            response = await client.get(api_url, timeout=30.0, headers=headers)
            
            if response.status_code != 200:
                return JSONResponse(
                    status_code=response.status_code,
                    content={
                        "error": f"GitHub API error: {response.status_code}",
                        "details": response.text[:200] if response.text else "No details"
                    }
                )
            
            files_data = response.json()
            json_files = [f["name"] for f in files_data if f["name"].endswith(".json")]
            
            if not json_files:
                return JSONResponse(
                    status_code=404,
                    content={"error": "No JSON files found in Data folder"}
                )
            
            imported = 0
            skipped = 0
            errors = 0
            entities_imported = set()
            
            for filename in json_files:
                try:
                    raw_url = f"https://raw.githubusercontent.com/Carrier0001/TheFirstCandle/main/Data/{filename}"
                    file_response = await client.get(raw_url, timeout=30.0, headers=headers)
                    
                    if file_response.status_code != 200:
                        errors += 1
                        continue
                    
                    data = file_response.json()
                    
                    if "entity_id" in data and "entries" in data:
                        entity_id = data["entity_id"]
                        entity_name = data.get("entity_name", entity_id.replace('_', ' ').title())
                        entities_imported.add(entity_name)
                        
                        for entry in data["entries"]:
                            # Skip entries with no harm/surplus
                            if (entry.get("harm_ly", 0) == 0 and 
                                entry.get("surplus_ly", 0) == 0 and 
                                not entry.get("description")):
                                skipped += 1
                                continue
                            
                            submission = {
                                "submission_id": entry.get("entry_id", str(uuid.uuid4())),
                                "submission_hash": hashlib.sha256(
                                    f"{entity_id}{entry.get('description', '')}{datetime.now()}".encode()
                                ).hexdigest(),
                                "entity_id": entity_id,
                                "entity_name": entity_name,
                                "title": f"{entity_name} - {entry.get('incident_type', 'Incident')}",
                                "description": entry.get("description", ""),
                                "incident_country": "Global",
                                "incident_year": entry.get("year", 2025),
                                "life_loss": abs(entry.get("harm_ly", 0)),
                                "financial_loss": abs(entry.get("harm_ecy", 0)),
                                "submitter_pubkey_hash": "web_import",
                                "status": "APPROVED",
                                "created_at": entry.get("date_logged", datetime.now().isoformat())
                            }
                            
                            try:
                                await ledger.submit_entry(submission)
                                imported += 1
                            except Exception as e:
                                errors += 1
                                
                    else:
                        errors += 1
                        
                except Exception as e:
                    errors += 1
            
            # Get final count
            all_submissions = await ledger.get_submissions()
            
            return JSONResponse(content={
                "message": "Import completed successfully",
                "imported": imported,
                "skipped": skipped,
                "errors": errors,
                "files_processed": len(json_files),
                "entities_imported": list(entities_imported),
                "total_submissions": len(all_submissions)
            })
            
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

# ==================== IMPORT SINGLE FILE (GROK AI) ====================
@app.get("/admin/import-grok")
async def import_grok():
    """Quick import just Grok AI data"""
    try:
        ledger = get_ledger()
        
        if not ledger:
            return JSONResponse(
                status_code=503,
                content={"error": "Ledger not ready"}
            )
        
        url = "https://raw.githubusercontent.com/Carrier0001/TheFirstCandle/main/Data/grok_ai.json"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            
            data = response.json()
            
            imported = 0
            if "entity_id" in data and "entries" in data:
                entity_id = data["entity_id"]
                entity_name = data["entity_name"]
                
                for entry in data["entries"]:
                    if (entry.get("harm_ly", 0) == 0 and 
                        entry.get("surplus_ly", 0) == 0 and 
                        not entry.get("description")):
                        continue
                    
                    submission = {
                        "submission_id": entry.get("entry_id", str(uuid.uuid4())),
                        "submission_hash": hashlib.sha256(
                            f"{entity_id}{entry.get('description', '')}{datetime.now()}".encode()
                        ).hexdigest(),
                        "entity_id": entity_id,
                        "entity_name": entity_name,
                        "title": f"{entity_name} - {entry.get('incident_type', 'Incident')}",
                        "description": entry.get("description", ""),
                        "incident_country": "Global",
                        "incident_year": entry.get("year", 2025),
                        "life_loss": abs(entry.get("harm_ly", 0)),
                        "financial_loss": abs(entry.get("harm_ecy", 0)),
                        "submitter_pubkey_hash": "web_import",
                        "status": "APPROVED",
                        "created_at": entry.get("date_logged", datetime.now().isoformat())
                    }
                    await ledger.submit_entry(submission)
                    imported += 1
            
            return JSONResponse(content={
                "message": f"✅ Imported {imported} entries for {entity_name}",
                "imported": imported,
                "entity": entity_name
            })
            
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

# ==================== CHECK LEDGER STATUS ====================
@app.get("/admin/status")
async def ledger_status():
    """Check ledger status and data count"""
    try:
        ledger = get_ledger()
        
        if not ledger:
            return JSONResponse(
                status_code=503,
                content={"error": "Ledger not ready"}
            )
        
        submissions = await ledger.get_submissions()
        entities = set()
        for sub in submissions:
            entities.add(sub.get('entity_id'))
        
        return JSONResponse(content={
            "ledger_ready": True,
            "total_submissions": len(submissions),
            "unique_entities": len(entities),
            "entities": list(entities)[:10]  # Show first 10
        })
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

# ==================== TEST ROUTE ====================
@app.get("/test")
async def test_page(request: Request):
    if not is_ledger_ready():
        return HTMLResponse("Ledger not ready", status_code=503)
    
    ledger = get_ledger()
    submissions_list = await ledger.get_submissions()
    return render("minimal.html", request, entity_count=len(submissions_list))

# ==================== PUBLIC LEDGER (HOME) ====================
@app.get("/", include_in_schema=False)
async def root(request: Request):
    if not is_ledger_ready():
        return render("index.html", request, entities=[], current_date=datetime.now().strftime("%B %d, %Y"))
    
    ledger = get_ledger()
    submissions_list = await ledger.get_submissions()
    
    # Aggregate submissions by entity
    entity_aggregates = {}
    for sub in submissions_list:
        if sub.get('status') == 'APPROVED':
            entity_id = sub.get('entity_id')
            if not entity_id:
                continue
            if entity_id not in entity_aggregates:
                entity_aggregates[entity_id] = {
                    "entity_id": entity_id,
                    "entity_name": sub.get('entity_name', 'Unknown'),
                    "total_entries": 0,
                    "total_harm_ly": 0,
                    "total_harm_ecy": 0,
                    "last_entry": None
                }
            
            entity_aggregates[entity_id]["total_entries"] += 1
            entity_aggregates[entity_id]["total_harm_ly"] += abs(sub.get('life_loss', 0))
            entity_aggregates[entity_id]["total_harm_ecy"] += abs(sub.get('financial_loss', 0))
            created_at = sub.get('created_at')
            if created_at and (entity_aggregates[entity_id]["last_entry"] is None or created_at > entity_aggregates[entity_id]["last_entry"]):
                entity_aggregates[entity_id]["last_entry"] = created_at
    
    entities_list = []
    for entity_id, data in entity_aggregates.items():
        entities_list.append({
            "entity_id": data["entity_id"],
            "entity_name": data["entity_name"],
            "lifetime": {
                "outstanding_ly": data["total_harm_ly"],
                "outstanding_ecy": data["total_harm_ecy"]
            },
            "total_entries": data["total_entries"],
            "measurement_date": data["last_entry"].strftime("%Y-%m-%d") if data["last_entry"] else datetime.now().strftime("%Y-%m-%d"),
            "has_systemic": False
        })
    
    # Sort by harm (most harmful first)
    entities_list.sort(key=lambda x: x["lifetime"]["outstanding_ly"], reverse=True)
    
    return render("index.html", request, entities=entities_list, current_date=datetime.now().strftime("%B %d, %Y"))

# ==================== ENTITY DETAIL PAGE ====================
@app.get("/entity/{entity_id}", include_in_schema=False)
async def entity_page(request: Request, entity_id: str):
    if not is_ledger_ready():
        return render("entity.html", request, entity={
            "entity_id": entity_id,
            "entity_name": "Loading...",
            "entity_state": "PENDING",
            "measurement_date": datetime.now().strftime("%Y-%m-%d"),
            "entries": [],
            "aggregated_entries": []
        })
    
    ledger = get_ledger()
    submissions_list = await ledger.get_submissions(entity_id)
    
    if not submissions_list:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    # Filter only approved submissions
    approved_submissions = [s for s in submissions_list if s.get('status') == 'APPROVED']
    
    if not approved_submissions:
        raise HTTPException(status_code=404, detail="No approved submissions found for this entity")
    
    entity_data = {
        "entity_id": entity_id,
        "entity_name": approved_submissions[0].get('entity_name', 'Unknown'),
        "entity_state": "ACTIVE",
        "measurement_date": datetime.now().strftime("%Y-%m-%d"),
        "entries": [],
        "aggregated_entries": []
    }
    
    for sub in approved_submissions:
        entity_data["entries"].append({
            "entry_id": sub.get('submission_id', ''),
            "year": sub.get('incident_year', 0),
            "description": sub.get('description', ''),
            "harm_ly": sub.get('life_loss', 0),
            "harm_ecy": sub.get('financial_loss', 0.0),
            "intent_type": "NEGLIGENCE",
            "confidence": "MEDIUM",
            "evidence_hashes": []
        })
    
    return render("entity.html", request, entity=entity_data)

# ==================== INDIVIDUAL ENTRY PAGE ====================
@app.get("/entity/{entity_id}/entry/{entry_id}", include_in_schema=False)
async def entry_page(request: Request, entity_id: str, entry_id: str):
    if not is_ledger_ready():
        raise HTTPException(status_code=503, detail="Ledger initializing, please refresh")
    
    ledger = get_ledger()
    submission = await ledger.get_submission(entry_id)
    
    if not submission or submission.get('entity_id') != entity_id or submission.get('status') != 'APPROVED':
        raise HTTPException(status_code=404, detail="Entry not found")
    
    entry_data = {
        "entry_id": submission.get('submission_id', ''),
        "year": submission.get('incident_year', 0),
        "description": submission.get('description', ''),
        "harm_ly": submission.get('life_loss', 0),
        "harm_ecy": submission.get('financial_loss', 0.0),
        "intent_type": "NEGLIGENCE",
        "confidence": "MEDIUM",
        "evidence_hashes": [],
        "external_links": []
    }
    
    entity_data = {
        "entity_id": submission.get('entity_id', ''),
        "entity_name": submission.get('entity_name', 'Unknown')
    }
    
    return render("entry.html", request, entry=entry_data, entity=entity_data)

# ==================== INFO PAGES ====================
@app.get("/info", include_in_schema=False)
async def info(request: Request):
    return render("info.html", request)

@app.get("/methodology", include_in_schema=False)
async def methodology(request: Request):
    return render("methodology.html", request)

@app.get("/submit", include_in_schema=False)
async def submit(request: Request):
    return render("submit.html", request)

@app.get("/success", include_in_schema=False)
async def success(request: Request, submission_id: str = None, entity_name: str = None):
    return render("submit_success.html", request, submission_id=submission_id, entity_name=entity_name)

# ==================== ADMIN UI ROUTES ====================

# Your admin secret (use environment variable)
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "admin123")

@app.get("/admin/{secret}/pending")
async def admin_pending(request: Request, secret: str):
    """View pending submissions (admin UI)"""
    
    # Security check
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")
    
    ledger = get_ledger()
    if not ledger:
        return render("error.html", request, error="Ledger not ready")
    
    # Get all submissions
    all_submissions = await ledger.get_submissions()
    
    # Filter pending ones
    pending = [s for s in all_submissions if s.get('status') == 'PENDING_JURY']
    
    # Format for the template - matches exactly what your template expects
    formatted_submissions = []
    for sub in pending:
        # Get evidence (if stored in submission)
        evidence_files = []
        evidence_links = []
        
        # Check if evidence is stored in the submission
        if 'evidence_links' in sub and sub['evidence_links']:
            if isinstance(sub['evidence_links'], list):
                evidence_links = sub['evidence_links']
            elif isinstance(sub['evidence_links'], str):
                evidence_links = [sub['evidence_links']]
        
        formatted_submissions.append({
            "filename": sub.get('submission_id', ''),
            "submission_id": sub.get('submission_id', ''),
            "entity": {
                "entity_id": sub.get('entity_id', ''),
                "entity_name": sub.get('entity_name', 'Unknown')
            },
            "event": {
                "year": sub.get('incident_year', 0),
                "description": sub.get('description', '')
            },
            "harm": {
                "life_loss": sub.get('life_loss', 0),
                "financial_loss": sub.get('financial_loss', 0)
            },
            "evidence": {
                "files": evidence_files,
                "links": evidence_links
            },
            "received_at": sub.get('created_at', ''),
            "status": sub.get('status', 'PENDING_JURY')
        })
    
    return render("admin_pending.html", request, 
                  submissions=formatted_submissions,
                  secret=secret)

@app.get("/admin/{secret}/review/{submission_id}")
async def admin_review(request: Request, secret: str, submission_id: str):
    """View a single pending submission for review"""
    
    # Security check
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")
    
    ledger = get_ledger()
    if not ledger:
        return render("error.html", request, error="Ledger not ready")
    
    submission = await ledger.get_submission(submission_id)
    
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    if submission.get('status') != 'PENDING_JURY':
        raise HTTPException(status_code=400, detail="Submission is not pending")
    
    # Get evidence
    evidence_files = []
    evidence_links = []
    
    if 'evidence_links' in submission and submission['evidence_links']:
        if isinstance(submission['evidence_links'], list):
            evidence_links = submission['evidence_links']
        elif isinstance(submission['evidence_links'], str):
            evidence_links = [submission['evidence_links']]
    
    # Format for the template - matches exactly what your review template expects
    formatted = {
        "filename": submission.get('submission_id', ''),
        "submission_id": submission.get('submission_id', ''),
        "entity": {
            "entity_id": submission.get('entity_id', ''),
            "entity_name": submission.get('entity_name', 'Unknown')
        },
        "event": {
            "year": submission.get('incident_year', 0),
            "description": submission.get('description', '')
        },
        "harm": {
            "life_loss": submission.get('life_loss', 0),
            "financial_loss": submission.get('financial_loss', 0),
            "ecosystem_loss": 0
        },
        "surplus": {
            "life_saved": 0,
            "financial_surplus": 0,
            "ecosystem_surplus": 0
        },
        "intent_type": "NEGLIGENCE",
        "evidence": {
            "files": evidence_files,
            "links": evidence_links
        },
        "received_at": submission.get('created_at', ''),
        "status": submission.get('status', 'PENDING_JURY')
    }
    
    return render("admin_review.html", request, 
                  submission=formatted,
                  secret=secret)

@app.post("/admin/{secret}/approve/{submission_id}")
async def admin_approve(request: Request, secret: str, submission_id: str):
    """Approve a submission and inscribe it in the ledger"""
    
    # Security check
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")
    
    ledger = get_ledger()
    if not ledger:
        return render("error.html", request, error="Ledger not ready")
    
    # Get form data
    form = await request.form()
    
    # Get current submission
    submission = await ledger.get_submission(submission_id)
    
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    if submission.get('status') != 'PENDING_JURY':
        raise HTTPException(status_code=400, detail="Submission is not pending")
    
    # Update with form data
    import sqlite3
    db_path = Path("./ledger/ledger.db")
    
    if not db_path.exists():
        return render("error.html", request, error="Database not found")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get updated values from form
    life_loss = int(form.get("life", submission.get('life_loss', 0)) or 0)
    financial_loss = float(form.get("financial", submission.get('financial_loss', 0)) or 0)
    ecosystem_loss = float(form.get("ecosystem", 0) or 0)
    intent_type = form.get("intent_type", "NEGLIGENCE")
    flag_spam = "flag_spam" in form
    
    # Update the submission
    cursor.execute("""
        UPDATE submissions 
        SET life_loss = ?,
            financial_loss = ?,
            intent_type = ?,
            status = 'APPROVED'
        WHERE submission_id = ?
    """, (life_loss, financial_loss, intent_type, submission_id))
    
    conn.commit()
    conn.close()
    
    # Get updated submission
    updated = await ledger.get_submission(submission_id)
    
    # Redirect back to pending list with success message
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ background: #1a1410; color: #f4efe8; font-family: system-ui; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
            .message {{ text-align: center; }}
            .message h1 {{ color: #e3b04b; font-size: 3rem; }}
            .message p {{ color: #cbbfae; font-size: 1.2rem; }}
            .message a {{ color: #e3b04b; text-decoration: none; border: 1px solid #e3b04b; padding: 0.8rem 2rem; border-radius: 8px; display: inline-block; margin-top: 1.5rem; }}
            .message a:hover {{ background: #e3b04b; color: #1a1410; }}
        </style>
    </head>
    <body>
        <div class="message">
            <h1>✅ Approved & Inscribed</h1>
            <p>The testimony has been verified and inscribed into the ledger.</p>
            <a href="/admin/{secret}/pending">← Back to Pending</a>
        </div>
    </body>
    </html>
    """)

@app.post("/admin/{secret}/reject/{submission_id}")
async def admin_reject(request: Request, secret: str, submission_id: str):
    """Reject a submission"""
    
    # Security check
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")
    
    ledger = get_ledger()
    if not ledger:
        return render("error.html", request, error="Ledger not ready")
    
    submission = await ledger.get_submission(submission_id)
    
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    if submission.get('status') != 'PENDING_JURY':
        raise HTTPException(status_code=400, detail="Submission is not pending")
    
    # Update status to REJECTED
    import sqlite3
    db_path = Path("./ledger/ledger.db")
    
    if not db_path.exists():
        return render("error.html", request, error="Database not found")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE submissions 
        SET status = 'REJECTED'
        WHERE submission_id = ?
    """, (submission_id,))
    
    conn.commit()
    conn.close()
    
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ background: #1a1410; color: #f4efe8; font-family: system-ui; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
            .message {{ text-align: center; }}
            .message h1 {{ color: #c94b4b; font-size: 3rem; }}
            .message p {{ color: #cbbfae; font-size: 1.2rem; }}
            .message a {{ color: #cbbfae; text-decoration: none; border: 1px solid #cbbfae; padding: 0.8rem 2rem; border-radius: 8px; display: inline-block; margin-top: 1.5rem; }}
            .message a:hover {{ background: #cbbfae; color: #1a1410; }}
        </style>
    </head>
    <body>
        <div class="message">
            <h1>❌ Rejected</h1>
            <p>The testimony has been rejected and will not be inscribed.</p>
            <a href="/admin/{secret}/pending">← Back to Pending</a>
        </div>
    </body>
    </html>
    """)

@app.get("/admin/{secret}/create-test")
async def create_test_pending(request: Request, secret: str):
    """Create a test pending submission for demo purposes"""
    
    # Security check
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")
    
    ledger = get_ledger()
    if not ledger:
        return JSONResponse(status_code=503, content={"error": "Ledger not ready"})
    
    test_submission = {
        "submission_id": f"test_{uuid.uuid4().hex[:8]}",
        "submission_hash": hashlib.sha256(f"test{datetime.now()}".encode()).hexdigest(),
        "entity_id": "test_entity",
        "entity_name": "Test Entity",
        "title": "Test Submission - Pending Review",
        "description": "This is a test submission awaiting jury review. It demonstrates the admin review workflow.",
        "incident_country": "Global",
        "incident_year": 2024,
        "life_loss": 0,
        "financial_loss": 0,
        "submitter_pubkey_hash": "test_user",
        "status": "PENDING_JURY",
        "created_at": datetime.now().isoformat()
    }
    
    await ledger.submit_entry(test_submission)
    
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ background: #1a1410; color: #f4efe8; font-family: system-ui; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
            .message {{ text-align: center; }}
            .message h1 {{ color: #e3b04b; font-size: 3rem; }}
            .message p {{ color: #cbbfae; font-size: 1.2rem; }}
            .message a {{ color: #e3b04b; text-decoration: none; border: 1px solid #e3b04b; padding: 0.8rem 2rem; border-radius: 8px; display: inline-block; margin-top: 1.5rem; }}
            .message a:hover {{ background: #e3b04b; color: #1a1410; }}
        </style>
    </head>
    <body>
        <div class="message">
            <h1>✅ Test Submission Created</h1>
            <p>A test pending submission has been created for review.</p>
            <a href="/admin/{secret}/pending">→ View Pending</a>
        </div>
    </body>
    </html>
    """)
