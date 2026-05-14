import os
import hashlib
import re
import json
from fastapi import Request, UploadFile, HTTPException, status
from app.core.config import config

def hash_ip_subnet(ip: str) -> str:
    try:
        octets = ip.split('.')[:3]
        subnet = ".".join(octets if len(octets) == 3 else ["0", "0", "0"])
    except:
        subnet = "0.0.0"
    return hashlib.blake2b(f"{subnet}{config.IP_SALT}".encode(), digest_size=32).hexdigest()

def hash_pubkey(pubkey: str) -> str:
    return hashlib.blake2b(pubkey.encode(), digest_size=32).hexdigest()

def hash_submission(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

def get_client_ip(request: Request) -> str:
    headers = request.headers
    for header in ['cf-connecting-ip', 'x-real-ip', 'x-forwarded-for']:
        if header in headers:
            ip = headers[header].split(',')[0].strip()
            if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                return ip
    return request.client.host or "0.0.0.0"

def validate_file_upload(file: UploadFile) -> tuple[bool, str]:
    if file.size and file.size > config.MAX_FILE_SIZE_MB * 1024 * 1024:
        return False, f"File too large (max {config.MAX_FILE_SIZE_MB}MB)"
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in config.ALLOWED_FILE_EXTENSIONS:
        return False, f"File type not allowed: {ext}"
    if file.content_type not in config.ALLOWED_MIME_TYPES:
        return False, f"MIME type not allowed: {file.content_type}"
    return True, ""