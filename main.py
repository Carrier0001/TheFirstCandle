import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.core.database import lifespan, get_ledger
from app.api import health, submissions, entities, aggregation, evidence, jury, admin
from datetime import datetime

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
