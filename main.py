import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.core.database import lifespan
from app.api import health, submissions, entities, aggregation, evidence, jury, admin

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
    return templates.TemplateResponse("index.html", {"request": request})

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