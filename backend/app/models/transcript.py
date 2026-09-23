from datetime import datetime
from typing import Literal, Self
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.video import utc_now


class TranscriptRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    language: str | None = Field(default=None, pattern=r'^[a-z]{2,3}$')


class Segment(BaseModel):
    id: int = Field(ge=0)
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)
    text: str = Field(min_length=1)

    @model_validator(mode='after')
    def valid_interval(self) -> Self:
        if self.end <= self.start or not self.text.strip():
            raise ValueError('Segment must have a positive duration and nonblank text')
        return self


class TranscriptResult(BaseModel):
    language: str | None
    duration_seconds: float = Field(gt=0, allow_inf_nan=False)
    segments: list[Segment]
    provider: str
    provider_version: str
    model: str
    model_revision: str
    engine_version: str
    adapter_version: str = 'faster-whisper-v1'
    parameters: dict[str, str | int | float | bool | None]

    @model_validator(mode='after')
    def valid_segments(self) -> Self:
        previous_end = 0.0
        for index, segment in enumerate(self.segments):
            if segment.id != index or segment.start < previous_end:
                raise ValueError('Segments must have consecutive IDs and non-overlapping timestamps')
            if segment.end > self.duration_seconds + 0.05:
                raise ValueError('Segment exceeds audio duration')
            previous_end = segment.end
        return self

    @property
    def text(self) -> str:
        return ' '.join(segment.text for segment in self.segments)


class TranscriptRun(BaseModel):
    id: UUID
    video_id: UUID
    status: Literal['processing', 'completed', 'failed'] = 'processing'
    created_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    requested_language: str | None = None
    requested_model: str
    requested_revision: str
    audio_sha256: str
    elapsed_seconds: float | None = None
    result: TranscriptResult | None = None
    text: str = ''
    error_code: str | None = None
    error_message: str | None = None
