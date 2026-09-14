from uuid import UUID
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from app.api.limits import UploadLimits
from app.database.repository import JsonVideoRepository, VideoRepository
from app.media.ffmpeg import FFmpegProcessor, MediaProcessor
from app.models.video import HealthResponse, VideoRecord
from app.shared.config import Settings
from app.shared.errors import ServiceError
from app.storage.local import LocalVideoStorage, VideoStorage
from app.videos.service import VideoService

def create_app(
    settings: Settings | None = None, *,
    storage: VideoStorage | None = None,
    repository: VideoRepository | None = None,
    media: MediaProcessor | None = None,
) -> FastAPI:
    config = settings or Settings.from_env()
    service = VideoService(
        config, storage or LocalVideoStorage(config.storage_root),
        repository or JsonVideoRepository(config.storage_root),
        media or FFmpegProcessor(config),
    )
    app = FastAPI(title="VerifiStream", version="0.1.0")
    app.add_middleware(
        UploadLimits, max_bytes=config.max_video_bytes + 64 * 1024,
        slots=config.max_concurrent_uploads,
    )

    @app.exception_handler(ServiceError)
    async def service_error(request: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(
            {"detail": {"code": exc.code, "message": exc.message}},
            status_code=exc.status_code,
        )

    @app.exception_handler(OSError)
    async def storage_error(request: Request, exc: OSError) -> JSONResponse:
        return JSONResponse(
            {"detail": {"code": "storage_error", "message": "Storage operation failed."}},
            status_code=503,
        )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """Liveness only; does not guarantee storage/media-tool readiness."""
        return HealthResponse()

    @app.post(
        "/videos", response_model=VideoRecord, status_code=201,
        openapi_extra={"requestBody": {"required": True, "content": {
            "multipart/form-data": {"schema": {"type": "object",
                "required": ["file"], "properties": {
                    "file": {"type": "string", "format": "binary"}}}}}}},
    )
    async def upload_video(request: Request) -> VideoRecord:
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "multipart/form-data":
            raise ServiceError("multipart_required", "Send multipart/form-data with one file field.", 415)
        async with request.form(max_files=1, max_fields=0) as form:
            uploaded = form.get("file")
            if not isinstance(uploaded, UploadFile) or not uploaded.filename or len(form) != 1:
                raise ServiceError("file_required", "Provide exactly one video in the file field.")
            return await run_in_threadpool(
                service.upload, uploaded.file, uploaded.filename,
                uploaded.content_type or "application/octet-stream",
            )

    @app.get("/videos/{video_id}", response_model=VideoRecord)
    def get_video(video_id: UUID) -> VideoRecord:
        return service.get(video_id)

    return app

app = create_app()
