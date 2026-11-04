"""Single-process exclusion between video requests and destructive deletion."""

from contextlib import contextmanager
from threading import Lock
from uuid import UUID
from pydantic import BaseModel, ConfigDict
from typing import Literal
from starlette.responses import JSONResponse
from app.shared.errors import ServiceError
from app.database.repository import VideoRepository
from app.storage.local import VideoStorage


class ClearVideosRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation: Literal["DELETE_ALL_VIDEOS"]
    video_ids: list[UUID]


class DeletionPreview(BaseModel):
    video_ids: list[UUID]
    count: int


class DeletionResult(BaseModel):
    deleted_ids: list[UUID]
    pending_cleanup: bool = False


class VideoActivity:
    def __init__(self):
        self.lock = Lock()
        self.active = 0
        self.deleting = False

    @contextmanager
    def exclusive(self):
        with self.lock:
            if self.active or self.deleting:
                raise ServiceError(
                    "videos_busy",
                    "Video requests are active. Wait for processing to finish, then retry deletion.",
                    409,
                )
            self.deleting = True
        try:
            yield
        finally:
            with self.lock:
                self.deleting = False


class VideoActivityMiddleware:
    def __init__(self, app, activity: VideoActivity):
        self.app, self.activity = app, activity

    async def __call__(self, scope, receive, send):
        guarded = (
            scope["type"] == "http"
            and (
                scope.get("path") == "/videos"
                or scope.get("path", "").startswith("/videos/")
            )
            and scope.get("method") in ("GET", "POST")
        )
        if not guarded:
            return await self.app(scope, receive, send)
        with self.activity.lock:
            blocked = self.activity.deleting
            if not blocked:
                self.activity.active += 1
        if blocked:
            return await JSONResponse(
                {
                    "detail": {
                        "code": "videos_deleting",
                        "message": "Video deletion is in progress; retry shortly.",
                    }
                },
                status_code=409,
            )(scope, receive, send)
        try:
            await self.app(scope, receive, send)
        finally:
            with self.activity.lock:
                self.activity.active -= 1


class VideoDeletionService:
    def __init__(
        self, videos: VideoRepository, storage: VideoStorage, activity: VideoActivity
    ):
        self.videos, self.storage, self.activity = videos, storage, activity

    def preview(self) -> DeletionPreview:
        ids = []
        offset = 0
        while True:
            batch = self.videos.list(100, offset)
            ids.extend(v.id for v in batch)
            if len(batch) < 100:
                break
            offset += 100
        return DeletionPreview(video_ids=sorted(ids, key=str), count=len(ids))

    def delete(self, video_id: UUID) -> DeletionResult:
        with self.activity.exclusive():
            if self.videos.get(video_id) is None:
                raise ServiceError("video_not_found", "Video was not found.", 404)
            purged = self.storage.delete(video_id)
            return DeletionResult(deleted_ids=[video_id], pending_cleanup=not purged)

    def clear(self, request: ClearVideosRequest) -> DeletionResult:
        with self.activity.exclusive():
            current = self.preview().video_ids
            if len(set(request.video_ids)) != len(request.video_ids) or set(
                current
            ) != set(request.video_ids):
                raise ServiceError(
                    "video_inventory_changed",
                    "The video library changed. Preview and confirm again.",
                    409,
                )
            pending = not self.storage.cleanup_deleted()
            deleted = []
            for video_id in current:
                # A storage error stops the operation; already deleted records stay removed.
                purged = self.storage.delete(video_id)
                pending = pending or not purged
                deleted.append(video_id)
            return DeletionResult(deleted_ids=deleted, pending_cleanup=pending)
