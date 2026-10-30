import json
import logging
import time
from threading import BoundedSemaphore
from uuid import UUID, uuid4
from app.database.repository import VideoRepository
from app.models.confidence import ConfidenceRequest, ConfidenceRun
from app.models.verification import VerificationRun
from app.models.video import utc_now
from app.confidence.algorithm import ConfidenceAlgorithm
from app.confidence.repository import ConfidenceRepository
from app.verification.repository import VerificationRepository
from app.verification.policy import SelectedEvidencePolicy
from app.verification.service import validate_ranking
from app.retrieval.fetcher import RetrievalError
from app.retrieval.service import digest
from app.shared.errors import ServiceError

logger = logging.getLogger('verifistream')


def validate_verification(source: VerificationRun, video_id: UUID) -> None:
    ranking = source.ranking_snapshot
    if (source.video_id != video_id or source.request.ranking_run_id != ranking.id
            or source.ranking_sha256 != digest(ranking) or ranking.status != 'completed'):
        raise ValueError('Invalid verification lineage')
    validate_ranking(ranking, video_id)
    policy = SelectedEvidencePolicy()
    if source.policy_version != policy.version or source.parameters != policy.parameters:
        raise ServiceError('unsupported_verification_version',
                           'Cannot score this verification version or parameter set.', 409)
    if source.results != policy.evaluate(ranking):
        raise ValueError('Verification does not match replayed evidence')


class ConfidenceService:
    def __init__(self, videos: VideoRepository, verifications: VerificationRepository,
                 repository: ConfidenceRepository, algorithm: ConfidenceAlgorithm):
        self.videos,self.verifications,self.repository,self.algorithm=videos,verifications,repository,algorithm
        self.capacity=BoundedSemaphore(1)

    def _video(self,video_id: UUID) -> None:
        if self.videos.get(video_id) is None:
            raise ServiceError('video_not_found','Video was not found.',404)

    def create(self,video_id: UUID,request: ConfidenceRequest) -> ConfidenceRun:
        self._video(video_id)
        if not self.capacity.acquire(blocking=False):
            raise ServiceError('confidence_busy','Another confidence is running; retry later.',503)
        try:
            source=self.verifications.get(video_id,request.verification_run_id)
            if source is None:
                raise ServiceError('verification_not_found','Verification was not found.',404)
            if source.status!='completed':
                raise ServiceError('verification_not_ready','Select a completed verification run.',409)
            source=source.model_copy(deep=True)
            try:
                if source.id!=request.verification_run_id:
                    raise ValueError('Verification ID mismatch')
                validate_verification(source,video_id)
            except (ValueError,RetrievalError) as exc:
                raise ServiceError('invalid_source_lineage','Saved verification evidence is inconsistent.',409) from exc
            run=ConfidenceRun(id=uuid4(),video_id=video_id,request=request.model_copy(deep=True),
                verification_snapshot=source,verification_sha256=digest(source),algorithm_version=self.algorithm.version,
                parameters=dict(self.algorithm.parameters),warnings=[
                    'Evidence Confidence is an uncalibrated evidence adequacy heuristic, not probability of truth.',
                    'Inspect components, caps, unknown signals and the saved verification citations.',
                    'No status is changed and no additional evidence is retrieved.'])
            self.repository.save(run)
            started=time.monotonic()
            logger.info(json.dumps({'event':'confidence_started','run_id':str(run.id)}))
            try:
                run.results=self.algorithm.evaluate(source)
                run.status='completed'
            except Exception:
                run.status,run.error_code='failed','confidence_failed'
                run.results=[]
            run.finished_at=utc_now()
            run.elapsed_seconds=round(time.monotonic()-started,3)
            self.repository.save(run)
            logger.info(json.dumps({'event':'confidence_finished','run_id':str(run.id),
                                   'status':run.status,'elapsed_seconds':run.elapsed_seconds}))
            return run
        finally:
            self.capacity.release()

    def list(self,video_id: UUID) -> list[ConfidenceRun]:
        self._video(video_id)
        return self.repository.list(video_id)

    def get(self,video_id: UUID,run_id: UUID) -> ConfidenceRun:
        self._video(video_id)
        run=self.repository.get(video_id,run_id)
        if run is None:
            raise ServiceError('confidence_not_found','Confidence was not found.',404)
        return run
