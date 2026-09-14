from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4
from app.models.video import VideoRecord

class VideoRepository(Protocol):
    def save(self, record: VideoRecord) -> None: ...
    def get(self, video_id: UUID) -> VideoRecord | None: ...

class JsonVideoRepository:
    """Single-host development adapter; replace with PostgreSQL for durable jobs."""
    def __init__(self, root: Path):
        self.root = root

    def save(self, record: VideoRecord) -> None:
        target = self.root / str(record.id) / "metadata.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(f"metadata-{uuid4()}.tmp")
        try:
            temp.write_text(record.model_dump_json(indent=2), encoding="utf-8")
            temp.replace(target)
        finally:
            temp.unlink(missing_ok=True)

    def get(self, video_id: UUID) -> VideoRecord | None:
        path = self.root / str(video_id) / "metadata.json"
        try:
            return VideoRecord.model_validate_json(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
