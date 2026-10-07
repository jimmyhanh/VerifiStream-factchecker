from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4
from app.models.retrieval import RetrievalRun


class RetrievalRepository(Protocol):
    def save(self, run: RetrievalRun) -> None: ...
    def get(self, video_id: UUID, run_id: UUID) -> RetrievalRun | None: ...
    def list(self, video_id: UUID) -> list[RetrievalRun]: ...


class JsonRetrievalRepository:
    """Single-process development adapter; no cross-process write coordination."""
    def __init__(self, root: Path):
        self.root = root

    def _directory(self, video_id: UUID) -> Path:
        return self.root / str(video_id) / 'retrievals'

    def save(self, run: RetrievalRun) -> None:
        existing = self.get(run.video_id, run.id)
        if existing is not None and existing.status != 'processing':
            raise ValueError('Cannot overwrite a terminal retrieval')
        directory = self._directory(run.video_id)
        directory.mkdir(parents=True, exist_ok=True)
        temporary = directory / f'{uuid4()}.tmp'
        try:
            temporary.write_text(run.model_dump_json(indent=2), encoding='utf-8')
            temporary.replace(directory / f'{run.id}.json')
        finally:
            temporary.unlink(missing_ok=True)

    def get(self, video_id: UUID, run_id: UUID) -> RetrievalRun | None:
        try:
            text = (self._directory(video_id) / f'{run_id}.json').read_text(encoding='utf-8')
        except FileNotFoundError:
            return None
        return RetrievalRun.model_validate_json(text)

    def list(self, video_id: UUID) -> list[RetrievalRun]:
        runs = [RetrievalRun.model_validate_json(path.read_text(encoding='utf-8'))
                for path in self._directory(video_id).glob('*.json')]
        return sorted(runs, key=lambda run: (run.created_at, str(run.id)), reverse=True)
