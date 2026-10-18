"""Evidence relationships are interpretations, never aggregate verdicts."""
from datetime import datetime
from typing import Literal, Self
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.retrieval import RetrievalRun
from app.models.video import utc_now

Relationship = Literal['SUPPORTS', 'CONTRADICTS', 'QUALIFIES', 'CONTEXT', 'IRRELEVANT']


class MappingRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    retrieval_run_id: UUID
    passage_ids: list[UUID] = Field(min_length=1, max_length=12)

    @model_validator(mode='after')
    def unique_selection(self) -> Self:
        if len(set(self.passage_ids)) != len(self.passage_ids):
            raise ValueError('Passage IDs must be unique')
        return self


class MappingDecision(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    status: Literal['mapped', 'needs_review']
    relationship: Relationship | None
    explanation: str = Field(min_length=1, max_length=1200)
    evidence_quote: str | None = Field(max_length=1000)
    caveats: list[str] = Field(max_length=8)
    causal_basis: Literal['explicit_causal_evidence', 'observational_only', 'not_applicable', 'unclear']

    @model_validator(mode='after')
    def consistent(self) -> Self:
        if not self.explanation.strip() or any(not s.strip() or len(s) > 400 for s in self.caveats):
            raise ValueError('Empty or excessive explanation/caveat')
        if self.status == 'mapped' and (self.relationship is None or not self.evidence_quote or not self.evidence_quote.strip()):
            raise ValueError('Mapped decisions require a relationship and quotation')
        if self.status == 'needs_review' and self.relationship is not None:
            raise ValueError('Abstentions must not assign a relationship')
        return self


class MappingResult(BaseModel):
    proposition_id: UUID
    passage_id: UUID
    source_id: UUID
    status: Literal['mapped', 'needs_review', 'failed']
    decision: MappingDecision | None = None
    citation_url: str
    quote_char_start: int | None = None
    quote_char_end: int | None = None
    returned_model: str | None = None
    provider_response_id: str | None = None
    usage: dict[str, int] = Field(default_factory=dict)
    error_code: str | None = None


class MappingRun(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: UUID
    video_id: UUID
    request: MappingRequest
    retrieval_snapshot: RetrievalRun
    retrieval_sha256: str
    status: Literal['processing', 'completed', 'partial', 'failed'] = 'processing'
    created_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    elapsed_seconds: float | None = None
    pipeline_version: str = 'evidence-mapping-v1'
    provider: str
    requested_model: str
    prompt_version: str
    prompt_snapshot: str
    parameters: dict[str, str | int | float | bool]
    results: list[MappingResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
