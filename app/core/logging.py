import logging
import json
from datetime import datetime, timezone
from app.core.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vow_ledger_v1")

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **getattr(record, "extra", {})
        }
        return json.dumps(log_data)

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.handlers = [handler]
logger.propagate = False

def log_audit(action: str, actor_hash: str, actor_type: str, **kwargs):
    logger.info(action, extra={
        "action": action,
        "actor_hash": actor_hash,
        "actor_type": actor_type,
        **kwargs
    })