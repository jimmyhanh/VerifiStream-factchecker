from datetime import datetime
from typing import Literal, Self
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.claim import ClaimRun
from app.models.video import utc_now


class ProposedProposition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=600)
    kind: Literal["factual", "observed_outcome", "causal"]
    needs_context: bool
    scope_notes: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def meaningful(self) -> Self:
        if (
            not self.text.strip()
            or len(self.text.split()) > 75
            or any(not note.strip() or len(note) > 500 for note in self.scope_notes)
        ):
            raise ValueError("Provide nonblank text and bounded scope notes")
        return self


class DraftDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    propositions: list[ProposedProposition] = Field(max_length=8)
    review_reason: str | None = Field(default=None, max_length=1000)


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_run_id: UUID
    candidate_ids: list[UUID] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len(set(self.candidate_ids)) != len(self.candidate_ids):
            raise ValueError("Candidate IDs must be unique")
        return self


class DraftResult(BaseModel):
    candidate_id: UUID
    source_quote: str
    status: Literal["proposed", "needs_review", "failed"]
    propositions: list[ProposedProposition] = Field(default_factory=list)
    review_reason: str | None = None
    error_code: str | None = None
    returned_model: str | None = None
    response_id: str | None = None
    usage: dict[str, int] = Field(default_factory=dict)


class DraftRun(BaseModel):
    id: UUID
    video_id: UUID
    request: DraftRequest
    claim_snapshot: ClaimRun
    claim_snapshot_sha256: str
    status: Literal["processing", "completed", "partial", "failed"] = "processing"
    provider: str
    requested_model: str
    prompt_version: str
    prompt_snapshot: str
    created_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    results: list[DraftResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ReviewedItem(ProposedProposition):
    candidate_id: UUID


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_run_id: UUID
    draft_run_id: UUID | None = None
    items: list[ReviewedItem] = Field(min_length=1, max_length=30)
    meaning_preserved: Literal[True]

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len({i.candidate_id for i in self.items}) > 10:
            raise ValueError("Review at most ten candidates")
        if len({(i.candidate_id, i.text.strip()) for i in self.items}) != len(
            self.items
        ):
            raise ValueError("Duplicate proposition for the same candidate")
        return self
