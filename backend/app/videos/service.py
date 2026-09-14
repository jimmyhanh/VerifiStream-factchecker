import json
import logging
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4
from app.database.repository import VideoRepository
from app.media.ffmpeg import MediaProcessor
from app.models.video import VideoRecord, VideoStatus, utc_now
from app.shared.config import Settings
from app.shared.errors import ServiceError
from app.storage.local import VideoStorage

logger = logging.getLogger("verifistream")
ALLOWED_TYPES = {
    ".mp4": {"video/mp4", "application/octet-stream"},
    ".mov": {"video/quicktime", "application/octet-stream"},
    ".webm": {"video/webm", "application/octet-stream"},
    ".mkv": {"video/x-matroska", "application/octet-stream"},
}

class VideoService:
    def __init__(self, settings: Settings, storage: VideoStorage,
                 repository: VideoRepository, media: MediaProcessor):
        self.settings = settings
        self.storage = storage
        self.repository = repository
        self.media = media

    def upload(self, stream: BinaryIO, filename: str, content_type: str) -> VideoRecord:
        # Normalize only display metadata; local paths always come from the UUID.
        name = filename.replace("\\", "/").rsplit("/", 1)[-1]
        extension = Path(name).suffix.lower()
        if len(name) > 255 or extension not in ALLOWED_TYPES:
            raise ServiceError("unsupported_video_type", "Use MP4, MOV, WebM, or MKV.", 415)
        if content_type.lower().split(";")[0].strip() not in ALLOWED_TYPES[extension]:
            raise ServiceError("unsupported_media_type", "Content type does not match the video extension.", 415)
        video_id = uuid4()
        try:
            size, digest = self.storage.save(video_id, stream, self.settings.max_video_bytes)
            duration = self.media.probe(self.storage.input_path(video_id), extension)
        except Exception:
            self.storage.remove(video_id)
            raise
        record = VideoRecord(
            id=video_id, original_filename=name, size_bytes=size,
            sha256=digest, duration_seconds=duration,
        )
        try:
            self.repository.save(record)
        except Exception:
            self.storage.remove(video_id)
            raise
        self._log(record, "extraction_started")
        try:
            record.extraction = self.media.extract(
                self.storage.input_path(video_id), self.storage.audio_path(video_id))
            record.status = VideoStatus.completed
        except ServiceError as exc:
            record.status = VideoStatus.failed
            record.error_code = exc.code
            record.error_message = exc.message
        except Exception:
            record.status = VideoStatus.failed
            record.error_code = "processing_error"
            record.error_message = "Audio extraction failed."
        record.updated_at = utc_now()
        self.repository.save(record)
        self._log(record, "extraction_finished")
        return record

    def get(self, video_id: UUID) -> VideoRecord:
        record = self.repository.get(video_id)
        if record is None:
            raise ServiceError("video_not_found", "Video was not found.", 404)
        return record

    @staticmethod
    def _log(record: VideoRecord, event: str) -> None:
        logger.info(json.dumps({
            "event": event, "video_id": str(record.id), "status": record.status.value,
            "error_code": record.error_code, "timestamp": utc_now().isoformat(),
        }))
