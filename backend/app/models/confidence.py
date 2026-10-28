from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.verification import EvidenceStatus, VerificationRun
from app.models.video import utc_now


class ConfidenceRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    verification_run_id: UUID


class ConfidenceComponent(BaseModel):
    value: float = Field(ge=0, le=1)
    weight: int = Field(ge=0, le=100)
    points: float = Field(ge=0, le=100)
    explanation: str


class ConfidenceCap(BaseModel):
    maximum: int = Field(ge=0, le=100)
    reason: str


class PropositionConfidence(BaseModel):
    proposition_id: UUID
    evidence_status: EvidenceStatus
    label: Literal['Evidence Confidence'] = 'Evidence Confidence'
    evidence_confidence: int = Field(ge=0, le=100)
    scope: Literal['selected_retrieved_evidence'] = 'selected_retrieved_evidence'
    calibrated: Literal[False] = False
    components: dict[str, ConfidenceComponent]
    raw_score: float = Field(ge=0, le=100)
    caps: list[ConfidenceCap]
    unknown_signals: dict[str, None]
    limitations: list[str]


class ConfidenceRun(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: UUID
    video_id: UUID
    request: ConfidenceRequest
    verification_snapshot: VerificationRun
    verification_sha256: str
    algorithm_version: str
    parameters: dict[str, str | int | float | bool]
    status: Literal['processing', 'completed', 'failed'] = 'processing'
    created_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    elapsed_seconds: float | None = None
    results: list[PropositionConfidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None = None
