# VerifiStream — evidence-based fact checker

Semester project, September–December 2026. **Milestone 1 only:** uploaded video
to extracted audio. Transcription, claims, retrieval, verification, confidence
and the frontend are not implemented.

## Run with Docker (recommended)
Install Docker with Compose, then run from the repository root:

```sh
git clone https://github.com/jimmyhanh/VerifiStream-factchecker.git
cd VerifiStream-factchecker
git checkout milestone-1-video-ingestion
docker compose up --build
```

Open http://localhost:8000/docs for the interactive upload API.
Health: http://localhost:8000/health.
Compose stores media in a named volume and binds the API to localhost.
To override limits, copy .env.example to .env and edit values before starting.
The Docker image includes FFmpeg and runs the API as a non-root user.

## Local development
Requires Python 3.11+ and FFmpeg/FFprobe on PATH.
On Ubuntu/Debian: `sudo apt-get update && sudo apt-get install -y ffmpeg`.
On macOS with Homebrew: `brew install ffmpeg`.
On Windows, install FFmpeg and add its bin directory to PATH; check both
`ffmpeg -version` and `ffprobe -version` before starting Python.

From the repository root:
```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e './backend[dev]'
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --log-config backend/logging.json
```

Windows PowerShell activation: `.venv\Scripts\Activate.ps1`.
Environment settings are read from the process. Local Python does **not**
automatically load .env. Example: `export MAX_VIDEO_BYTES=52428800` in
bash or `$env:MAX_VIDEO_BYTES="52428800"` in PowerShell.
Default storage is relative to the working directory: run from the repository root.

## API examples
```sh
curl http://localhost:8000/health
curl -F "file=@sample.mp4;type=video/mp4" http://localhost:8000/videos
curl http://localhost:8000/videos/REPLACE_WITH_RETURNED_UUID
```
On Windows PowerShell use `curl.exe` for these examples.

POST /videos receives one multipart field named `file`.
Allowed containers: MP4, MOV, WebM, MKV. Default maximum: 100 MiB and
600 seconds; the file must contain both video and audio.
application/octet-stream is accepted for supported extensions, but FFprobe
still validates the actual container/streams.

POST waits for extraction and returns HTTP 201 with a created video resource:
```json
{
  "id": " UUID ",
  "status": "completed",
  "original_filename": "sample.mp4",
  "size_bytes": 12345,
  "sha256": "...",
  "created_at": "...",
  "updated_at": "...",
  "duration_seconds": 1.0,
  "extraction": {
    "adapter_version": "ffmpeg-wav-v1",
    "ffmpeg_version": "ffmpeg version ...",
    "sample_rate": 16000,
    "channels": 1,
    "codec": "pcm_s16le"
  },
  "error_code": null,
  "error_message": null
}
```
The illustrative UUID/timestamps/hash above are placeholders.
A valid upload whose extraction fails also returns 201, with status `failed`
and a safe error_code/error_message. Callers must inspect `status`.
GET /videos/{id} reads persisted processing/completed/failed state.
No audio download endpoint is included; output is stored locally as
`storage/{uuid}/audio.wav`. Original media is `storage/{uuid}/original`.

Validation errors: 413 size limit, 415 unsupported type, 422 invalid media,
400 malformed/excess multipart fields. Lookup: 404 unknown UUID, 422 malformed UUID.
Probe timeout/tool absence: 504/503. Storage failures: 503.
Capacity is limited to two simultaneous uploads; excess requests receive
503 with Retry-After. The full request allows 64 KiB of multipart overhead
in addition to the configured file limit. Error responses use detail.code
and detail.message for application errors; framework validation errors have
FastAPI/Starlette's standard detail shape.
Health is liveness only, not a check of FFmpeg/storage readiness.

## Tests
```sh
cd backend
python -m pytest -q
```
Run from the activated environment after the editable install.
Unit/API tests use injected media adapters. Integration tests synthesize a
one-second video using FFmpeg, upload it through the API and inspect the WAV.
They also reject silent and fake videos. Integration tests skip if FFmpeg
or FFprobe is absent; CI explicitly installs both.
GitHub Actions runs the entire suite and starts a real Uvicorn server for
an HTTP health smoke test. See docs/progress.md for observed execution status.
A separate CI job builds Docker Compose and uploads a generated video through
the running container, verifying both FFmpeg availability and storage permissions.

## Layout
- backend/app/api: HTTP limits
- backend/app/videos: orchestration
- backend/app/media: FFprobe/FFmpeg adapter and protocol
- backend/app/storage: storage protocol and local adapter
- backend/app/database: repository protocol and JSON development adapter
- backend/app/models and shared: schemas, configuration and errors
- backend/tests: API, unit and integration tests
- docs: architecture, roadmap and progress
- evaluation: future evaluation contract
- storage: ignored local media

## Current limitations
Local development only: no authentication, user isolation, quotas or retention UI.
Use one Uvicorn process. Upload admission limits are process-local.
Synchronous extraction can outlast proxy timeouts; there is no durable queue,
retry or recovery. A process crash may leave processing records and orphan files.
Local metadata survives normal restarts, but is not a transactional database.
PostgreSQL is deferred behind the repository interface until persistent jobs
or multi-process operation are introduced.
Request pre-buffering and multipart parsing may use two temporary disk copies;
budget disk space for concurrent maximum-sized uploads. No upload idle timeout
is provided by the application; configure one at an ingress before public use.
FFmpeg has bounded wall time and output size, but this is not a hostile-media
sandbox. Run isolated workers with OS resource limits before accepting public
uploads. Only the first audio stream is extracted; no language/track selection.
Dependency ranges are bounded, not a fully locked reproducible environment yet.
No political-bias scoring and no verification based on model memory.

Next milestone: replaceable transcription adapter with timestamped segments.
