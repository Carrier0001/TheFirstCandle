from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator
from app.models.enums import *

class SubmitTestimonyRequest(BaseModel):
    entity_id: str = Field(..., min_length=3, max_length=100)
    entity_name: str = Field(..., min_length=2, max_length=200)
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=10, max_length=10000)
    incident_country: str = Field(..., min_length=2, max_length=100)
    incident_state: Optional[str] = None
    incident_city: Optional[str] = None
    incident_year: int = Field(..., ge=1900, le=datetime.now().year)
    life_loss: int = Field(0, ge=0)
    financial_loss: float = Field(0.0, ge=0)
    ecosystem_loss: Optional[str] = None
    num_victims: int = Field(0, ge=0)

    @validator('entity_id')
    def normalize_entity_id(cls, v):
        return v.lower().replace(' ', '_').replace('-', '_')

class SubmissionResponse(BaseModel):
    submission_id: str
    submission_hash: str
    entity_id: str
    status: SubmissionStatus
    created_at: datetime

    class Config:
        from_attributes = True  # Allow UUID to str conversion

class SystemicPatternResponse(BaseModel):
    systemic_pattern_id: str
    entity_id: str
    pattern_hash: str
    description_summary: str
    entry_count: int
    total_harm_ly: float
    total_financial_usd: float
    total_harm_ecy: float
    total_affected: int
    pattern_confidence: str
    created_at: datetime

class EntryDetailResponse(BaseModel):
    entry_id: str
    entity_id: str
    title: str
    description: str
    status: EntryStatus
    depth_level: int
    harm_ly: float
    financial_usd: float
    harm_ecy: float
    num_affected: int
    intent_type: HarmType
    confidence: Confidence
    jury_consensus_votes: int
    jury_total_votes: int
    systemic_key: Optional[str] = None
    created_at: datetime
    locked_at: Optional[datetime] = None