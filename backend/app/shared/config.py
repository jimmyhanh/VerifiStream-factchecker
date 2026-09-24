import os
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field

class Settings(BaseModel):
    storage_root: Path = Path("storage")
    max_video_bytes: int = Field(default=100 * 1024 * 1024, gt=0)
    max_duration_seconds: int = Field(default=600, gt=0)
    process_timeout_seconds: int = Field(default=120, gt=0)
    max_concurrent_uploads: int = Field(default=2, gt=0, le=16)
    transcription_model: Literal['tiny', 'base', 'small'] = 'base'
    transcription_revision: str = 'main'
    model_cache: Path = Path('storage/models')
    transcription_timeout_seconds: int = Field(default=900, gt=0)
    transcription_threads: int = Field(default=4, gt=0, le=32)
    max_claim_transcript_chars: int = Field(default=100000, gt=0, le=1000000)
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            storage_root=os.getenv("STORAGE_ROOT", "storage"),
            max_video_bytes=os.getenv("MAX_VIDEO_BYTES", "104857600"),
            max_duration_seconds=os.getenv("MAX_DURATION_SECONDS", "600"),
            process_timeout_seconds=os.getenv("PROCESS_TIMEOUT_SECONDS", "120"),
            max_concurrent_uploads=os.getenv("MAX_CONCURRENT_UPLOADS", "2"),
            transcription_model=os.getenv('TRANSCRIPTION_MODEL', 'base'),
            transcription_revision=os.getenv('TRANSCRIPTION_MODEL_REVISION', 'main'),
            model_cache=os.getenv('MODEL_CACHE', 'storage/models'),
            transcription_timeout_seconds=os.getenv('TRANSCRIPTION_TIMEOUT_SECONDS', '900'),
            transcription_threads=os.getenv('TRANSCRIPTION_THREADS', '4'),
            max_claim_transcript_chars=os.getenv('MAX_CLAIM_TRANSCRIPT_CHARS', '100000'),
            ffmpeg=os.getenv("FFMPEG_BINARY", "ffmpeg"),
            ffprobe=os.getenv("FFPROBE_BINARY", "ffprobe"),
        )
