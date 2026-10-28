import json
import logging
import time
from threading import BoundedSemaphore
from uuid import UUID, uuid4
from app.database.repository import VideoRepository
from app.models.ranking import RankingRun
from app.models.verification import VerificationRequest, VerificationRun
from app.models.video import utc_now
from app.ranking.algorithm import TransparentRankingAlgorithm
from app.ranking.repository import RankingRepository
from app.ranking.service import validate_mapping, validate_annotations
from app.retrieval.fetcher import RetrievalError
from app.retrieval.service import digest
from app.shared.errors import ServiceError
from app.verification.policy import VerificationPolicy
from app.verification.repository import VerificationRepository

logger = logging.getLogger('verifistream')


def validate_ranking(ranking: RankingRun, video_id: UUID) -> None:
    mapping = ranking.mapping_snapshot
    if (ranking.video_id!=video_id or ranking.request.mapping_run_id!=mapping.id
            or ranking.mapping_sha256!=digest(mapping)
            or mapping.status not in ('completed','partial')):
        raise ValueError('Invalid ranking lineage')
    pairs = validate_mapping(mapping,video_id)
    validate_annotations(ranking.request,mapping,pairs)
    algorithm = TransparentRankingAlgorithm()
    if (ranking.ranking_version!=algorithm.ranking_version
            or ranking.grouping_version!=algorithm.grouping_version
            or ranking.parameters!=algorithm.parameters):
        raise ServiceError('unsupported_ranking_version','Cannot verify this ranking version or parameter set.',409)
    groups, results = algorithm.analyze(mapping,ranking.request)
    if ranking.groups!=groups or ranking.results!=results:
        raise ValueError('Ranking does not match replayed evidence')


class VerificationService:
    def __init__(self, videos: VideoRepository, rankings: RankingRepository,
                 repository: VerificationRepository, policy: VerificationPolicy):
        self.videos,self.rankings,self.repository,self.policy=videos,rankings,repository,policy
        self.capacity=BoundedSemaphore(1)

    def _video(self,video_id: UUID) -> None:
        if self.videos.get(video_id) is None:
            raise ServiceError('video_not_found','Video was not found.',404)

    def create(self,video_id: UUID,request: VerificationRequest) -> VerificationRun:
        self._video(video_id)
        if not self.capacity.acquire(blocking=False):
            raise ServiceError('verification_busy','Another verification is running; retry later.',503)
        try:
            source=self.rankings.get(video_id,request.ranking_run_id)
            if source is None:
                raise ServiceError('ranking_not_found','Ranking was not found.',404)
            if source.status!='completed':
                raise ServiceError('ranking_not_ready','Select a completed ranking run.',409)
            source=source.model_copy(deep=True)
            try:
                if source.id!=request.ranking_run_id:
                    raise ValueError('Ranking ID mismatch')
                validate_ranking(source,video_id)
            except (ValueError,RetrievalError) as exc:
                raise ServiceError('invalid_source_lineage','Saved ranking evidence is inconsistent.',409) from exc
            run=VerificationRun(id=uuid4(),video_id=video_id,request=request.model_copy(deep=True),
                ranking_snapshot=source,ranking_sha256=digest(source),policy_version=self.policy.version,
                parameters=dict(self.policy.parameters),warnings=[
                    'Evidence statuses apply only to the selected retrieved evidence, not universal truth.',
                    'Inherited model mappings can be wrong; inspect citations, caveats and scope.',
                    'Dependence groups are not independent confirmations; no majority vote is used.',
                    'completed means processing finished, not that every proposition has sufficient evidence.',
                    'No aggregate compound-claim verdict or Evidence Confidence is calculated.'])
            self.repository.save(run)
            started=time.monotonic()
            logger.info(json.dumps({'event':'verification_started','run_id':str(run.id)}))
            try:
                run.results=self.policy.evaluate(source)
                run.status='completed'
            except Exception:
                run.status,run.error_code='failed','verification_failed'
                run.results=[]
            run.finished_at=utc_now()
            run.elapsed_seconds=round(time.monotonic()-started,3)
            self.repository.save(run)
            logger.info(json.dumps({'event':'verification_finished','run_id':str(run.id),
                                   'status':run.status,'elapsed_seconds':run.elapsed_seconds}))
            return run
        finally:
            self.capacity.release()

    def list(self,video_id: UUID) -> list[VerificationRun]:
        self._video(video_id)
        return self.repository.list(video_id)

    def get(self,video_id: UUID,run_id: UUID) -> VerificationRun:
        self._video(video_id)
        run=self.repository.get(video_id,run_id)
        if run is None:
            raise ServiceError('verification_not_found','Verification was not found.',404)
        return run
