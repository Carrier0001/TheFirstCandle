import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.core.database import lifespan
from app.api import health, submissions, entities, aggregation, evidence, jury, admin
from app.core.database import db_pool  # Add this import

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

@app.get("/", include_in_schema=False)
async def root(request: Request):
    # Fetch approved submissions from database
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT submission_id, entity_name, title, description, 
                   incident_country, incident_year, created_at, received_at,
                   life_loss_submitted, financial_loss_submitted, evidence_links
            FROM submissions 
            WHERE status = 'APPROVED'
            ORDER BY received_at DESC
            LIMIT 50
        """)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "entries": rows
    })

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
