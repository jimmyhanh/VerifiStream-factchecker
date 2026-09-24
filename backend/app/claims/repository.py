from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4
from app.models.claim import ClaimRun


class ClaimRepository(Protocol):
    def save(self, run: ClaimRun) -> None: ...
    def get(self, video_id: UUID, run_id: UUID) -> ClaimRun | None: ...
    def list(self, video_id: UUID) -> list[ClaimRun]: ...


class JsonClaimRepository:
    """Single-process development adapter; no cross-process write coordination."""
    def __init__(self, root: Path):
        self.root = root

    def _directory(self, video_id: UUID) -> Path:
        return self.root / str(video_id) / 'claim-extractions'

    def save(self, run: ClaimRun) -> None:
        existing = self.get(run.video_id, run.id)
        if existing is not None and existing.status != 'processing':
            raise ValueError('Cannot overwrite a terminal claim extraction')
        directory = self._directory(run.video_id)
        directory.mkdir(parents=True, exist_ok=True)
        temporary = directory / f'{uuid4()}.tmp'
        try:
            temporary.write_text(run.model_dump_json(indent=2), encoding='utf-8')
            temporary.replace(directory / f'{run.id}.json')
        finally:
            temporary.unlink(missing_ok=True)

    def get(self, video_id: UUID, run_id: UUID) -> ClaimRun | None:
        try:
            text = (self._directory(video_id) / f'{run_id}.json').read_text(encoding='utf-8')
        except FileNotFoundError:
            return None
        return ClaimRun.model_validate_json(text)

    def list(self, video_id: UUID) -> list[ClaimRun]:
        runs = [ClaimRun.model_validate_json(path.read_text(encoding='utf-8'))
                for path in self._directory(video_id).glob('*.json')]
        return sorted(runs, key=lambda run: (run.created_at, str(run.id)), reverse=True)
