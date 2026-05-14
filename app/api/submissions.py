from fastapi import APIRouter, Request, UploadFile, File, BackgroundTasks, Header, HTTPException, status, Form
from typing import List
import uuid
import hashlib
from datetime import datetime, timezone

from app.models.pydantic_models import SubmitTestimonyRequest, SubmissionResponse
from app.models.enums import SubmissionStatus
from app.core.security import (
    hash_pubkey, get_client_ip, hash_ip_subnet, hash_submission, validate_file_upload
)
from app.core import database
from app.core.logging import log_audit
from app.utils.background import check_auto_aggregation

router = APIRouter(prefix="/api/v1", tags=["submissions"])

@router.post("/submit", response_model=SubmissionResponse)
async def submit_testimony(
    request: Request,
    entity_id: str = Form(...),
    entity_name: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    incident_country: str = Form(...),
    incident_year: int = Form(...),
    incident_state: str = Form(default=None),
    incident_city: str = Form(default=None),
    life_loss: int = Form(default=0),
    financial_loss: float = Form(default=0.0),
    ecosystem_loss: str = Form(default=None),
    num_victims: int = Form(default=0),
    background_tasks: BackgroundTasks = None,
    files: List[UploadFile] = File(default=[]),
    x_submitter_pubkey: str = Header(default="test-submitter")
):
    body = SubmitTestimonyRequest(
        entity_id=entity_id,
        entity_name=entity_name,
        title=title,
        description=description,
        incident_country=incident_country,
        incident_state=incident_state,
        incident_city=incident_city,
        incident_year=incident_year,
        life_loss=life_loss,
        financial_loss=financial_loss,
        ecosystem_loss=ecosystem_loss,
        num_victims=num_victims
    )

    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Too many files (max 10)")

    for file in files:
        valid, msg = validate_file_upload(file)
        if not valid:
            raise HTTPException(status_code=400, detail=msg)

    client_ip = get_client_ip(request)
    submitter_hash = hash_pubkey(x_submitter_pubkey)
    submission_id = str(uuid.uuid4())
    submission_hash = hash_submission(body.dict())

    evidence_files = []
    for file in files:
        try:
            data = await file.read()
            file_hash = hashlib.sha256(data).hexdigest()
            ext = "." + file.filename.split(".")[-1].lower()
            storage_path = f"s3://vow-evidence/{submission_id}/{file_hash}{ext}"
            evidence_files.append({
                "hash": file_hash,
                "filename": file.filename,
                "size": len(data),
                "mime_type": file.content_type,
                "storage_path": storage_path
            })
        except Exception as e:
            log_audit("FILE_PROCESS_FAILED", submitter_hash, "SUBMITTER", error=str(e))

    async with database.db_pool.acquire() as conn:
        async with conn.transaction():
            existing = await conn.fetchval(
                "SELECT 1 FROM submissions WHERE submission_hash = $1", submission_hash
            )
            if existing:
                raise HTTPException(status_code=409, detail="Duplicate submission detected")

            result = await conn.fetchrow("""
                INSERT INTO submissions (
                    submission_id, submission_hash, entity_id, entity_name, title, description,
                    incident_country, incident_state, incident_city, incident_year,
                    life_loss_submitted, financial_loss_submitted, ecosystem_loss_submitted,
                    num_victims_submitted, submitter_pubkey_hash, client_ip_hash, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, 'PENDING_JURY')
                RETURNING submission_id, submission_hash, entity_id, status, received_at
            """, submission_id, submission_hash, body.entity_id, body.entity_name,
                body.title, body.description, body.incident_country,
                body.incident_state, body.incident_city, body.incident_year,
                body.life_loss, body.financial_loss, body.ecosystem_loss,
                body.num_victims, submitter_hash, hash_ip_subnet(client_ip))

            # Insert evidence files in same transaction
            if evidence_files:
                for f in evidence_files:
                    await conn.execute("""
                        INSERT INTO evidence_files (file_hash, submission_id, original_filename, file_size, mime_type, storage_location, pending)
                        VALUES ($1, $2, $3, $4, $5, $6, TRUE)
                        ON CONFLICT (file_hash) DO NOTHING
                    """, f['hash'], submission_id, f['filename'], f['size'], f['mime_type'], f['storage_path'])

            log_audit("SUBMISSION_CREATED", submitter_hash, "SUBMITTER",
                      submission_id=submission_id, entity=body.entity_name, evidence_count=len(evidence_files))

    background_tasks.add_task(check_auto_aggregation, body.entity_id)

    return SubmissionResponse(
    submission_id=str(result['submission_id']),
    submission_hash=result['submission_hash'],
    entity_id=result['entity_id'],
    status=SubmissionStatus[result['status']],
    created_at=result['received_at']
)