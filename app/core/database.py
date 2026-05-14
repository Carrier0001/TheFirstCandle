import asyncpg
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI

logger = logging.getLogger("vow")
db_pool = None


def get_secret(var_name: str, file_var_name: str = None) -> str:
    """Helper to read secrets from file (Docker) or env var."""
    # First check for _FILE version (Docker secrets)
    file_path = os.getenv(file_var_name) if file_var_name else os.getenv(f"{var_name}_FILE")
    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                value = f.read().strip()
            logger.info(f"Loaded secret {var_name} from file")
            return value
        except Exception as e:
            logger.error(f"Failed to read secret file {file_path}: {e}")

    # Fallback to direct environment variable
    value = os.getenv(var_name)
    if value:
        logger.info(f"Loaded secret {var_name} from environment")
        return value

    raise ValueError(f"Secret {var_name} not found in environment or secret file!")


async def init_db():
    global db_pool

    database_url = os.getenv("DATABASE_URL")
    
    # If no full DATABASE_URL is provided, build it from parts (more secure)
    if not database_url:
        db_user = "vow"
        db_host = "postgres"
        db_name = "vow"
        db_password = get_secret("DB_PASSWORD", "DB_PASSWORD_FILE")
        
        database_url = f"postgresql://{db_user}:{db_password}@{db_host}:5432/{db_name}"

    db_pool = await asyncpg.create_pool(
        database_url,
        min_size=5,
        max_size=20,
        command_timeout=60,
        server_settings={"application_name": "vow_ledger"},
    )
    logger.info("✅ Database connection pool initialized successfully")


async def close_db():
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("✅ Database connection pool closed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        logger.info("🚀 Vow Ledger v1.0 starting...")
        yield
    finally:
        await close_db()
        logger.info("🛑 Vow Ledger v1.0 shutting down...")
