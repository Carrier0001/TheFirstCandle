import asyncpg
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.config import config

logger = logging.getLogger("vow")
db_pool = None

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(
        config.DATABASE_URL,
        min_size=5,
        max_size=20,
        command_timeout=60,
    )
    logger.info("Database pool initialized")

async def close_db():
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("Database pool closed")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Vow Ledger v1.0 starting...")
    yield
    await close_db()
    logger.info("Vow Ledger v1.0 shutting down...")