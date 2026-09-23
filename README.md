# VerifiStream — evidence-based fact checker

Semester project, September–December 2026. **Milestones 1–2:** uploaded video to audio and timestamped transcription.
Claims, retrieval, verification, confidence and the frontend are not implemented.

## Run with Docker (recommended)
Install Docker with Compose, then run from the repository root:

```sh
git clone https://github.com/jimmyhanh/VerifiStream-factchecker.git
cd VerifiStream-factchecker
git checkout main
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
python -m pip install -e './backend[dev,transcription]'
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

Next milestone: detect check-worthy claims from timestamped transcripts.

## Milestone 2: timestamped transcription

After merging the Milestone 2 PR, update from the repository root:

```sh
git pull origin main
docker compose up --build
```

The existing media volume is reused. Do not run `docker compose down -v` if you
want to preserve uploads, transcripts and downloaded models.

Open http://localhost:8000/docs. Use an existing **actual video UUID** returned
by POST /videos, not the documentation's Example Value.

1. Expand **POST /videos/{video_id}/transcriptions**, click Try it out.
2. Enter the video UUID and use request body `{"language":"en"}` for English,
   `{"language":"vi"}` for Vietnamese, or `{}` to auto-detect the language.
3. Execute and wait. First use downloads the model; later requests reuse it.
4. HTTP 201 means a run was created. Check `status`: `completed` or `failed`.
5. Read `text` and `result.segments`, each with `id`, `start`, `end`, `text`.
   Times are seconds relative to the extracted audio/video timeline; segment
   IDs are local to that run. These are estimated ASR timestamps, not forced alignment.
6. GET /videos/{video_id}/transcript retrieves the latest **successful** run.
   GET /videos/{video_id}/transcriptions lists all attempts, newest first.
   GET /videos/{video_id}/transcriptions/{run_id} retrieves a specific attempt.

PowerShell example (replace YOUR_VIDEO_UUID):

```powershell
$videoId = "YOUR_VIDEO_UUID"
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/videos/$videoId/transcriptions" -ContentType "application/json" -Body '{"language":"en"}'
Invoke-RestMethod -Uri "http://localhost:8000/videos/$videoId/transcript"
```

An example segment shape (illustrative, not a result):
```json
{"id": 0, "start": 0.5, "end": 3.2, "text": "This is a sample sentence."}
```

### Local model and configuration
Default: Faster Whisper 1.2.1, multilingual **base**, CPU, int8, four threads.
No API key or external transcription API is used. Model files are downloaded
from Hugging Face; audio stays inside your local process/container.
The first run needs internet and additional disk/RAM. CPU speed varies; start
with a short speech clip. No real-time speed guarantee.

Set values in .env for Compose, then recreate with `docker compose up --build`:
- TRANSCRIPTION_MODEL: tiny, base (default), or small. Larger models generally
  cost more processing time and memory; validate accuracy on your own clips.
- TRANSCRIPTION_MODEL_REVISION: main by default; use a model commit SHA to pin it.
  An existing cached main snapshot is reused, including offline; change to an
  explicit revision to upgrade reproducibly. Each result records its resolved SHA.
- TRANSCRIPTION_TIMEOUT_SECONDS: 900 including model loading and inference.
- TRANSCRIPTION_THREADS: 4 by default.
- MODEL_CACHE: local Python path; Compose fixes this at /srv/storage/models.

Local Python needs `python -m pip install -e './backend[dev,transcription]'`.
PyAV is pinned to 16.1.0 because 18.1.0 crashed during import in the authoring
runtime. Normal API and unit tests do not import the native speech engine.

### Errors and limits
- 404: unknown video or no successful transcript yet.
- 409: extraction incomplete, or missing/invalid WAV.
- 422: malformed request, invalid UUID/language format or unknown JSON fields.
- 503 transcription_busy: another transcription is running; retry after it ends.
- HTTP 201 with status failed: inspect error_code and error_message. Common codes
  are model_unavailable, unsupported_language, transcription_timeout,
  provider_unavailable, invalid_transcript and transcription_failed.

Only one transcription runs per API process. POST waits for completion;
GET/health remain available. The provider runs in a subprocess that is killed
on timeout. There is no durable job queue or restart recovery yet. Reload/crash
may leave a processing record; a new POST creates a separate attempt.
Every attempt lives at storage/{video_id}/transcriptions/{run_id}.json.
Retries preserve old results. Empty detected speech produces a completed empty
transcript. ASR can mishear names, numbers, or speech and can hallucinate;
transcripts are not verified claims and have no Evidence Confidence score.
No diarization, word timestamps, translation, or frontend is added in M2.

### Real model smoke test
The normal suite can run without model downloads. To run the optional real-model
API test, download the short JFK fixture supplied by whisper.cpp:

```sh
curl -L --fail -o /tmp/jfk.wav https://raw.githubusercontent.com/ggerganov/whisper.cpp/master/samples/jfk.wav
ASR_TEST_AUDIO=/tmp/jfk.wav python -m pytest backend/tests -q
```

PowerShell: save the WAV to a local path, set `$env:ASR_TEST_AUDIO` to that path,
then run `python -m pytest backend/tests -q`.
CI enables this test and also transcribes spoken video through the built Docker
container. It checks an expected keyword, timestamps and silence behavior; this
is a smoke test, **not** an accuracy benchmark. See docs/progress.md for results.
Upstream provider documentation: https://github.com/SYSTRAN/faster-whisper.
