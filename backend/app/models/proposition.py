from datetime import datetime
from typing import Literal, Self
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.claim import ClaimProviderInfo, ClaimRun
from app.models.video import utc_now


class DecompositionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    claim_run_id: UUID | None = None
    candidate_ids: list[UUID] | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode='after')
    def unique_ids(self) -> Self:
        if self.candidate_ids and len(set(self.candidate_ids)) != len(self.candidate_ids):
            raise ValueError('Candidate IDs must be unique')
        return self


class TextSpan(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode='after')
    def interval(self) -> Self:
        if self.end <= self.start:
            raise ValueError('Empty source span')
        return self


class ClausePlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    subject: TextSpan
    predicate: TextSpan
    attribution: TextSpan | None = None
    context: TextSpan | None = None
    separate_effect: bool = False


class DecompositionPlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    clauses: list[ClausePlan] = Field(default_factory=list, max_length=10)
    review_reason: str | None = Field(default=None, max_length=300)

    @model_validator(mode='after')
    def exclusive_outcomes(self) -> Self:
        if bool(self.clauses) == bool(self.review_reason):
            raise ValueError('Return clauses or a review reason, exclusively')
        return self


class SourcePart(BaseModel):
    role: Literal['subject', 'predicate', 'attribution', 'context']
    char_start: int
    char_end: int
    quote: str


class AtomicProposition(BaseModel):
    id: UUID
    parent_candidate_id: UUID
    text: str
    kind: Literal['factual', 'observed_outcome', 'causal']
    transformation: Literal['source_clause', 'policy_change_outcome', 'policy_jobs_outcome']
    source_parts: list[SourcePart]
    source_quote: str
    segment_ids: list[int]
    start_seconds: float
    end_seconds: float
    attribution: str | None = None
    context: str | None = None
    needs_context: bool
    related_proposition_ids: list[UUID] = Field(default_factory=list)


class ParentDecomposition(BaseModel):
    parent_candidate_id: UUID
    source_quote: str
    status: Literal['unchanged', 'decomposed', 'needs_review']
    review_reason: str | None = None
    propositions: list[AtomicProposition] = Field(default_factory=list)


class DecompositionRun(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: UUID
    video_id: UUID
    claim_run_id: UUID
    transcript_run_id: UUID
    status: Literal['processing', 'completed', 'failed'] = 'processing'
    created_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    elapsed_seconds: float | None = None
    provider: ClaimProviderInfo
    pipeline_version: str = 'atomic-lineage-v1'
    claim_snapshot_sha256: str
    claim_snapshot: ClaimRun
    selected_candidate_ids: list[UUID]
    results: list[ParentDecomposition] = Field(default_factory=list)
    unresolved_count: int = 0
    proposition_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
