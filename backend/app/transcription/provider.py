import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Protocol
from pydantic import ValidationError
from app.models.transcript import TranscriptResult
from app.shared.config import Settings
from app.shared.errors import ServiceError


class TranscriptionProvider(Protocol):
    def transcribe(self, audio: Path, language: str | None) -> TranscriptResult: ...


class FasterWhisperProvider:
    """A process boundary allows a real timeout, including lazy segment iteration."""
    def __init__(self, settings: Settings):
        self.settings = settings

    def transcribe(self, audio: Path, language: str | None) -> TranscriptResult:
        options = {
            'model': self.settings.transcription_model,
            'revision': self.settings.transcription_revision,
            'cache': str(self.settings.model_cache.resolve()),
            'threads': self.settings.transcription_threads,
            'language': language,
        }
        with tempfile.TemporaryDirectory(prefix='verifistream-transcript-') as temporary:
            output = Path(temporary) / 'result.json'
            try:
                subprocess.run(
                    [sys.executable, '-m', 'app.transcription.worker', str(audio.resolve()),
                     str(output), json.dumps(options)],
                    check=True, timeout=self.settings.transcription_timeout_seconds,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except subprocess.TimeoutExpired as exc:
                raise ServiceError('transcription_timeout', 'Transcription timed out; try a shorter clip.', 504) from exc
            except subprocess.CalledProcessError as exc:
                raise ServiceError('transcription_failed', 'Transcription failed. Check model availability and audio.', 503) from exc
            try:
                payload = json.loads(output.read_text(encoding='utf-8'))
                if 'error_code' in payload:
                    messages = {
                        'provider_unavailable': 'Install the transcription dependencies and rebuild the container.',
                        'model_unavailable': 'Model could not be loaded. Check network access, model revision and cache permissions.',
                        'unsupported_language': 'The requested language is not supported by the model.',
                        'transcription_failed': 'The transcription engine could not process this audio.',
                    }
                    code = payload['error_code']
                    raise ServiceError(code if code in messages else 'transcription_failed',
                                       messages.get(code, 'Transcription failed.'), 503)
                return TranscriptResult.model_validate(payload)
            except (OSError, ValueError, ValidationError) as exc:
                raise ServiceError('invalid_transcript', 'Transcription returned invalid data.', 502) from exc
