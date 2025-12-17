import json
import hashlib
from typing import Dict, Any

def compute_lifetime_hash(lifetime: Dict[str, Any]) -> str:
    payload = json.dumps(lifetime, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

def seal_lifetime(entity: Dict[str, Any]) -> None:
    """
    Call ONLY when intentionally updating lifetime.
    """
    entity["lifetime_signature"] = compute_lifetime_hash(entity["lifetime"])

def verify_lifetime(entity: Dict[str, Any]) -> None:
    """
    Call on every load.
    """
    if "lifetime_signature" not in entity:
        raise ValueError("Missing lifetime signature")

    expected = compute_lifetime_hash(entity["lifetime"])
    if expected != entity["lifetime_signature"]:
        raise ValueError("🚨 LIFETIME TAMPERING DETECTED")