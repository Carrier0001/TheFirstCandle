import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.core.database import lifespan
from app.api import health, submissions, entities, aggregation, evidence, jury, admin
from app.core.database import db_pool
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
templates = Jinja2Templates(directory="templates")
templates.env.filters['comma_format'] = lambda x: f"{int(x):,}" if x else "0"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if os.getenv("ENVIRONMENT", "development") != "production" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(health.router)
app.include_router(submissions.router)
app.include_router(entities.router)
app.include_router(aggregation.router)
app.include_router(evidence.router)
app.include_router(jury.router)
app.include_router(admin.router)

# ==================== PUBLIC LEDGER (HOME) ====================
@app.get("/", include_in_schema=False)
async def root(request: Request):
    from datetime import datetime
    
    if db_pool is None:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "entities": [],
            "current_date": datetime.now().strftime("%B %d, %Y")
        })
    
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                entity_id,
                entity_name,
                COUNT(*) as total_entries,
                SUM(life_loss_submitted) as total_harm_ly,
                SUM(financial_loss_submitted) as total_harm_ecy,
                MAX(created_at) as last_entry
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
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "entities": entities,
        "current_date": datetime.now().strftime("%B %d, %Y")
    })

# ==================== ENTITY DETAIL PAGE ====================
@app.get("/entity/{entity_id}", include_in_schema=False)
async def entity_page(request: Request, entity_id: str):
    async with db_pool.acquire() as conn:
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
                created_at,
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
    
    return templates.TemplateResponse("entity.html", {
        "request": request,
        "entity": entity_data
    })

# ==================== INDIVIDUAL ENTRY PAGE ====================
@app.get("/entity/{entity_id}/entry/{entry_id}", include_in_schema=False)
async def entry_page(request: Request, entity_id: str, entry_id: str):
    async with db_pool.acquire() as conn:
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
                created_at,
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
    
    return templates.TemplateResponse("entry.html", {
        "request": request,
        "entry": entry_data,
        "entity": entity_data
    })

# ==================== INFO PAGES ====================
@app.get("/info", include_in_schema=False)
async def info(request: Request):
    return templates.TemplateResponse("info.html", {"request": request})

@app.get("/methodology", include_in_schema=False)
async def methodology(request: Request):
    return templates.TemplateResponse("methodology.html", {"request": request})

@app.get("/submit", include_in_schema=False)
async def submit(request: Request):
    return templates.TemplateResponse("submit.html", {"request": request})  

@app.get("/success", include_in_schema=False)
async def success(request: Request, submission_id: str = None, entity_name: str = None):
    return templates.TemplateResponse("submit_success.html", {
        "request": request,
        "submission_id": submission_id,
        "entity_name": entity_name
    })
