import os
import secrets
from dataclasses import dataclass

@dataclass
class Config:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://vow:password@postgres:5432/vow")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    PHONE_SALT: str = os.getenv("PHONE_SALT", "")
    IP_SALT: str = os.getenv("IP_SALT", "")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Settings
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
                raise ValueError(f"Missing required env vars in production: {missing}")
        else:
            if not self.JWT_SECRET:
                self.JWT_SECRET = secrets.token_hex(32)
            if not self.PHONE_SALT:
                self.PHONE_SALT = f"dev-phone-{secrets.token_hex(16)}"
            if not self.IP_SALT:
                self.IP_SALT = f"dev-ip-{secrets.token_hex(16)}"

config = Config()
config.validate()