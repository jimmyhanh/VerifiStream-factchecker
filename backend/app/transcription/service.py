import hashlib
import json
import logging
import time
import wave
from threading import BoundedSemaphore
from uuid import UUID, uuid4
from app.database.repository import VideoRepository
from app.models.transcript import TranscriptRequest, TranscriptRun
from app.models.video import VideoStatus, utc_now
from app.shared.config import Settings
from app.shared.errors import ServiceError
from app.storage.local import VideoStorage
from app.transcription.provider import TranscriptionProvider
from app.transcription.repository import TranscriptRepository

logger = logging.getLogger('verifistream')


class TranscriptionService:
    def __init__(self, settings: Settings, videos: VideoRepository, storage: VideoStorage,
                 transcripts: TranscriptRepository, provider: TranscriptionProvider):
        self.settings = settings
        self.videos = videos
        self.storage = storage
        self.transcripts = transcripts
        self.provider = provider
        self.capacity = BoundedSemaphore(1)

    def _video(self, video_id: UUID):
        video = self.videos.get(video_id)
        if video is None:
            raise ServiceError('video_not_found', 'Video was not found.', 404)
        return video

    def create(self, video_id: UUID, request: TranscriptRequest) -> TranscriptRun:
        run, _ = self.create_or_reuse(video_id, request)
        return run

    def create_or_reuse(self, video_id: UUID, request: TranscriptRequest) -> tuple[TranscriptRun, bool]:
        video = self._video(video_id)
        if video.status != VideoStatus.completed:
            raise ServiceError('audio_not_ready', 'Video audio extraction is not completed.', 409)
        if not self.capacity.acquire(blocking=False):
            raise ServiceError('transcription_busy', 'Another transcription is running; retry later.', 503)
        try:
            audio = self.storage.audio_path(video_id)
            if not audio.is_file():
                raise ServiceError('audio_missing', 'Extracted audio is missing.', 409)
            try:
                with wave.open(str(audio), 'rb') as stream:
                    duration = stream.getnframes() / stream.getframerate()
                    if (stream.getnchannels(), stream.getframerate(), stream.getsampwidth()) != (1, 16000, 2):
                        raise ValueError('Unexpected audio format')
                    if not 0 < duration <= self.settings.max_duration_seconds + 0.5:
                        raise ValueError('Unexpected duration')
            except (wave.Error, EOFError, ValueError) as exc:
                raise ServiceError('invalid_audio', 'Extracted audio is invalid.', 409) from exc
            with audio.open('rb') as source:
                digest = hashlib.file_digest(source, 'sha256').hexdigest()
            if request.reuse_completed:
                cached = self._matching_run(video_id, request.language, digest)
                if cached is not None:
                    logger.info(json.dumps({"event": "transcription_reused", "video_id": str(video_id),
                                            "run_id": str(cached.id)}))
                    return cached, True
            run = TranscriptRun(id=uuid4(), video_id=video_id,
                                requested_language=request.language,
                                requested_model=self.settings.transcription_model,
                                requested_revision=self.settings.transcription_revision,
                                audio_sha256=digest)
            self.transcripts.save(run)
            started = time.monotonic()
            logger.info(json.dumps({'event': 'transcription_started', 'video_id': str(video_id),
                                    'run_id': str(run.id)}))
            try:
                result = self.provider.transcribe(audio, request.language)
                if abs(result.duration_seconds - duration) > 0.05:
                    raise ServiceError('invalid_transcript', 'Transcript duration does not match the audio.', 502)
                run.result = result
                run.text = result.text
                run.status = 'completed'
            except ServiceError as exc:
                run.status = 'failed'
                run.error_code = exc.code
                run.error_message = exc.message
            except Exception:
                run.status = 'failed'
                run.error_code = 'transcription_failed'
                run.error_message = 'Transcription failed unexpectedly.'
            run.elapsed_seconds = round(time.monotonic() - started, 3)
            run.finished_at = utc_now()
            self.transcripts.save(run)
            logger.info(json.dumps({'event': 'transcription_finished', 'video_id': str(video_id),
                                    'run_id': str(run.id), 'status': run.status,
                                    'elapsed_seconds': run.elapsed_seconds, 'error_code': run.error_code}))
            return run, False
        finally:
            self.capacity.release()

    def _matching_run(self, video_id: UUID, language: str | None, audio_sha256: str) -> TranscriptRun | None:
        identify = getattr(self.provider, "reuse_identity", None)
        if identify is None:
            return None
        try:
            expected = identify(language)
        except Exception:
            # Identity lookup is optional; a missing model/cache/dependency must not
            # turn a cache miss into a failed transcription request.
            logger.info(json.dumps({"event": "transcription_identity_unavailable", "video_id": str(video_id)}))
            return None
        fields = {"provider", "provider_version", "model", "model_revision", "engine_version",
                  "adapter_version", "parameters"}
        if not isinstance(expected, dict) or set(expected) != fields:
            return None
        for run in self.transcripts.list(video_id):
            if (run.video_id == video_id and run.status == "completed" and run.result is not None
                    and run.audio_sha256 == audio_sha256 and run.requested_language == language
                    and run.requested_model == self.settings.transcription_model
                    and run.requested_revision == self.settings.transcription_revision
                    and run.result.model_dump(include=fields) == expected):
                return run
        return None

    def list(self, video_id: UUID) -> list[TranscriptRun]:
        self._video(video_id)
        return self.transcripts.list(video_id)

    def get(self, video_id: UUID, run_id: UUID) -> TranscriptRun:
        self._video(video_id)
        run = self.transcripts.get(video_id, run_id)
        if run is None:
            raise ServiceError('transcription_not_found', 'Transcription run was not found.', 404)
        return run

    def latest(self, video_id: UUID) -> TranscriptRun:
        for run in self.list(video_id):
            if run.status == 'completed':
                return run
        raise ServiceError('transcript_not_found', 'No successful transcript exists for this video.', 404)
