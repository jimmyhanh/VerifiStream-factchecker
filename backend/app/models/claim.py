from datetime import datetime
from typing import Literal, Self
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.transcript import TranscriptResult
from app.models.video import utc_now


class ClaimRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    transcript_run_id: UUID | None = None


class ClaimSpan(BaseModel):
    """Provider output: offsets into the canonical transcript, never paraphrases."""
    model_config = ConfigDict(extra='forbid', strict=True)
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    signals: list[Literal['numerical', 'causal', 'factual_event']] = Field(min_length=1, max_length=3)

    @model_validator(mode='after')
    def valid_span(self) -> Self:
        if self.char_end <= self.char_start or len(set(self.signals)) != len(self.signals):
            raise ValueError('Invalid span or duplicate signals')
        return self


class ClaimCandidate(ClaimSpan):
    id: UUID
    quote: str = Field(min_length=1)
    segment_ids: list[int] = Field(min_length=1)
    start_seconds: float = Field(ge=0, allow_inf_nan=False)
    end_seconds: float = Field(gt=0, allow_inf_nan=False)
    reason: str
    needs_context: bool


class ClaimProviderInfo(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    name: str
    version: str
    model: str | None = None
    prompt_version: str | None = None
    parameters: dict[str, str | int | float | bool]


class ClaimRun(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: UUID
    video_id: UUID
    transcript_run_id: UUID
    status: Literal['processing', 'completed', 'failed'] = 'processing'
    created_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    elapsed_seconds: float | None = None
    provider: ClaimProviderInfo
    pipeline_version: str = 'claim-spans-v1'
    transcript_sha256: str
    transcript_snapshot: TranscriptResult
    candidates: list[ClaimCandidate] = Field(default_factory=list, max_length=1000)
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
