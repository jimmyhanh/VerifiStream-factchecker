import hashlib
import shutil
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import UUID
from app.shared.errors import ServiceError

class VideoStorage(Protocol):
    def save(self, video_id: UUID, stream: BinaryIO, limit: int) -> tuple[int, str]: ...
    def input_path(self, video_id: UUID) -> Path: ...
    def audio_path(self, video_id: UUID) -> Path: ...
    def remove(self, video_id: UUID) -> None: ...

class LocalVideoStorage:
    def __init__(self, root: Path):
        self.root = root

    def input_path(self, video_id: UUID) -> Path:
        return self.root / str(video_id) / "original"

    def audio_path(self, video_id: UUID) -> Path:
        return self.root / str(video_id) / "audio.wav"

    def save(self, video_id: UUID, stream: BinaryIO, limit: int) -> tuple[int, str]:
        target = self.input_path(video_id)
        target.parent.mkdir(parents=True, exist_ok=False)
        temporary = target.with_suffix(".part")
        size = 0
        digest = hashlib.sha256()
        try:
            with temporary.open("xb") as output:
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > limit:
                        raise ServiceError("video_too_large", "Video exceeds configured size limit.", 413)
                    digest.update(chunk)
                    output.write(chunk)
            if size == 0:
                raise ServiceError("empty_video", "Video is empty.")
            temporary.replace(target)
        except Exception:
            self.remove(video_id)
            raise
        return size, digest.hexdigest()

    def remove(self, video_id: UUID) -> None:
        shutil.rmtree(self.root / str(video_id), ignore_errors=True)
