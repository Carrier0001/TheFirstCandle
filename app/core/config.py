import os
import secrets
from dataclasses import dataclass


def get_secret(var_name: str) -> str:
    """Read secret from _FILE (Docker secrets) or direct env var."""
    # Priority 1: Check for secret file (Docker)
    file_path = os.getenv(f"{var_name}_FILE")
    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                return f.read().strip()
        except Exception as e:
            print(f"⚠️ Failed to read secret file for {var_name}: {e}")

    # Priority 2: Direct environment variable
    value = os.getenv(var_name)
    if value:
        return value

    return ""


@dataclass
class Config:
    # Core settings
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Secrets (support both direct and _FILE)
    JWT_SECRET: str = get_secret("JWT_SECRET")
    PHONE_SALT: str = get_secret("PHONE_SALT")
    IP_SALT: str = get_secret("IP_SALT")

    # Application settings
    JWT_EXPIRE_HOURS: int = 24
    MAGIC_LINK_EXPIRE_HOURS: int = 24
    MAX_FILE_SIZE_MB: int = 25
    MAX_FILES_PER_SUBMISSION: int = 10
    JURY_POOL_SIZE: int = 12
    CONSENSUS_THRESHOLD: float = 0.58
    SIMILARITY_THRESHOLD: float = 0.65
    MIN_CASES_FOR_AGGREGATION: int = 2
    AUTO_AGGREGATE_DAYS: int = 30

    ALLOWED_FILE_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".txt", ".md", ".mp4", ".mp3", ".webm"}
    ALLOWED_MIME_TYPES = {
        "application/pdf", "image/jpeg", "image/png", "text/plain",
        "text/markdown", "video/mp4", "audio/mp3", "video/webm"
    }

    def validate(self):
        if self.ENVIRONMENT == "production":
            required = ["JWT_SECRET", "PHONE_SALT", "IP_SALT"]
            missing = [k for k in required if not getattr(self, k)]
            if missing:
                raise ValueError(f"❌ Missing required secrets in production: {missing}")
            
            if not self.DATABASE_URL and not os.getenv("DB_PASSWORD") and not os.getenv("DB_PASSWORD_FILE"):
                raise ValueError("❌ DATABASE_URL or DB_PASSWORD is required in production")
        else:
            # Development fallbacks
            if not self.JWT_SECRET:
                self.JWT_SECRET = secrets.token_hex(32)
            if not self.PHONE_SALT:
                self.PHONE_SALT = f"dev-phone-{secrets.token_hex(16)}"
            if not self.IP_SALT:
                self.IP_SALT = f"dev-ip-{secrets.token_hex(16)}"

        # Build DATABASE_URL if not provided
        if not self.DATABASE_URL:
            db_password = get_secret("DB_PASSWORD")
            if db_password:
                self.DATABASE_URL = f"postgresql://vow:{db_password}@postgres:5432/vow"
            else:
                self.DATABASE_URL = "postgresql://vow:password@postgres:5432/vow"  # fallback for local


config = Config()
config.validate()

print(f"✅ Config loaded successfully | Environment: {config.ENVIRONMENT}")
