from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4
from app.models.transcript import TranscriptRun


class TranscriptRepository(Protocol):
    def save(self, record: TranscriptRun) -> None: ...
    def get(self, video_id: UUID, run_id: UUID) -> TranscriptRun | None: ...
    def list(self, video_id: UUID) -> list[TranscriptRun]: ...


class JsonTranscriptRepository:
    def __init__(self, root: Path):
        self.root = root

    def _directory(self, video_id: UUID) -> Path:
        return self.root / str(video_id) / 'transcriptions'

    def save(self, record: TranscriptRun) -> None:
        directory = self._directory(record.video_id)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f'{record.id}.json'
        # Terminal runs are immutable; a retry always receives a new UUID.
        existing = self.get(record.video_id, record.id)
        if existing is not None and existing.status != 'processing':
            raise ValueError('Cannot overwrite a terminal transcription run')
        temporary = directory / f'{uuid4()}.tmp'
        try:
            temporary.write_text(record.model_dump_json(indent=2), encoding='utf-8')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)

    def get(self, video_id: UUID, run_id: UUID) -> TranscriptRun | None:
        try:
            content = (self._directory(video_id) / f'{run_id}.json').read_text(encoding='utf-8')
        except FileNotFoundError:
            return None
        return TranscriptRun.model_validate_json(content)

    def list(self, video_id: UUID) -> list[TranscriptRun]:
        records = [TranscriptRun.model_validate_json(path.read_text(encoding='utf-8'))
                   for path in self._directory(video_id).glob('*.json')]
        return sorted(records, key=lambda record: (record.created_at, str(record.id)), reverse=True)
