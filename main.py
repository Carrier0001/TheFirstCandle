import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.core.database import lifespan
from app.api import health, submissions, entities, aggregation, evidence, jury, admin
from app.core import database
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

def is_db_ready():
    return database.db_pool is not None and hasattr(database.db_pool, 'acquire')

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
    if not is_db_ready():
        return HTMLResponse("Database not ready", status_code=503)
    async with database.db_pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM submissions")
    return render("minimal.html", request, entity_count=count)

# ==================== PUBLIC LEDGER (HOME) ====================
@app.get("/", include_in_schema=False)
async def root(request: Request):
    if not is_db_ready():
        return render("index.html", request, entities=[], current_date=datetime.now().strftime("%B %d, %Y"))
    
    async with database.db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                entity_id,
                entity_name,
                COUNT(*) as total_entries,
                SUM(life_loss_submitted) as total_harm_ly,
                SUM(financial_loss_submitted) as total_harm_ecy,
                MAX(received_at) as last_entry
            FROM submissions 
            WHERE status = 'APPROVED'
            GROUP BY entity_id, entity_name
            ORDER BY total_harm_ly ASC
        """)
        
        entities = []
        for row in rows:
            entities.append({
                "entity_id": row['entity_id'],
                "entity_name": row['entity_name'],
                "lifetime": {
                    "outstanding_ly": abs(row['total_harm_ly'] or 0),
                    "outstanding_ecy": abs(row['total_harm_ecy'] or 0)
                },
                "total_entries": row['total_entries'],
                "measurement_date": row['last_entry'].strftime("%Y-%m-%d") if row['last_entry'] else datetime.now().strftime("%Y-%m-%d"),
                "has_systemic": False
            })
    
    return render("index.html", request, entities=entities, current_date=datetime.now().strftime("%B %d, %Y"))

# ==================== ENTITY DETAIL PAGE ====================
@app.get("/entity/{entity_id}", include_in_schema=False)
async def entity_page(request: Request, entity_id: str):
    if not is_db_ready():
        return render("entity.html", request, entity={
            "entity_id": entity_id,
            "entity_name": "Loading...",
            "entity_state": "PENDING",
            "measurement_date": datetime.now().strftime("%Y-%m-%d"),
            "entries": [],
            "aggregated_entries": []
        })
    
    async with database.db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                submission_id,
                entity_id,
                entity_name,
                title,
                description,
                incident_year as year,
                life_loss_submitted as harm_ly,
                financial_loss_submitted as harm_ecy,
                status,
                received_at,
                evidence_links,
                intent_type,
                confidence
            FROM submissions 
            WHERE entity_id = $1 AND status = 'APPROVED'
            ORDER BY incident_year DESC
        """, entity_id)
        
        if not rows:
            raise HTTPException(status_code=404, detail="Entity not found")
        
        entity_data = {
            "entity_id": entity_id,
            "entity_name": rows[0]['entity_name'],
            "entity_state": "ACTIVE",
            "measurement_date": datetime.now().strftime("%Y-%m-%d"),
            "entries": [],
            "aggregated_entries": []
        }
        
        for row in rows:
            entity_data["entries"].append({
                "entry_id": row['submission_id'],
                "year": row['year'],
                "description": row['description'],
                "harm_ly": row['harm_ly'] or 0,
                "harm_ecy": row['harm_ecy'] or 0,
                "intent_type": row['intent_type'] or "NEGLIGENCE",
                "confidence": row['confidence'] or "MEDIUM",
                "evidence_hashes": [row['evidence_links']] if row['evidence_links'] else []
            })
    
    return render("entity.html", request, entity=entity_data)

# ==================== INDIVIDUAL ENTRY PAGE ====================
@app.get("/entity/{entity_id}/entry/{entry_id}", include_in_schema=False)
async def entry_page(request: Request, entity_id: str, entry_id: str):
    if not is_db_ready():
        raise HTTPException(status_code=503, detail="Database initializing, please refresh")
    
    async with database.db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT 
                submission_id,
                entity_id,
                entity_name,
                title,
                description,
                incident_year as year,
                life_loss_submitted as harm_ly,
                financial_loss_submitted as harm_ecy,
                status,
                received_at,
                evidence_links,
                intent_type,
                confidence
            FROM submissions 
            WHERE entity_id = $1 AND submission_id = $2 AND status = 'APPROVED'
        """, entity_id, entry_id)
        
        if not row:
            raise HTTPException(status_code=404, detail="Entry not found")
        
        entry_data = {
            "entry_id": row['submission_id'],
            "year": row['year'],
            "description": row['description'],
            "harm_ly": row['harm_ly'] or 0,
            "harm_ecy": row['harm_ecy'] or 0,
            "intent_type": row['intent_type'] or "NEGLIGENCE",
            "confidence": row['confidence'] or "MEDIUM",
            "evidence_hashes": [],
            "external_links": [row['evidence_links']] if row['evidence_links'] else []
        }
        
        entity_data = {
            "entity_id": row['entity_id'],
            "entity_name": row['entity_name']
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