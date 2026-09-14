from datetime import datetime, timezone
from enum import Enum
from uuid import UUID
from pydantic import BaseModel, Field

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class VideoStatus(str, Enum):
    processing = "processing"
    completed = "completed"
    failed = "failed"

class ExtractionInfo(BaseModel):
    adapter_version: str = "ffmpeg-wav-v1"
    ffmpeg_version: str
    sample_rate: int = 16000
    channels: int = 1
    codec: str = "pcm_s16le"

class VideoRecord(BaseModel):
    id: UUID
    status: VideoStatus = VideoStatus.processing
    original_filename: str
    size_bytes: int = Field(gt=0)
    sha256: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    duration_seconds: float = Field(gt=0)
    extraction: ExtractionInfo | None = None
    error_code: str | None = None
    error_message: str | None = None

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
