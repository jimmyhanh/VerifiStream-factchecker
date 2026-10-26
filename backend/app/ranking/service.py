import json
import logging
import time
from threading import BoundedSemaphore
from uuid import UUID, uuid4
from app.database.repository import VideoRepository
from app.evidence.repository import MappingRepository
from app.evidence.service import validate_snapshot
from app.models.mapping import MappingRun, MappingDecision
from app.models.ranking import RankingRequest, RankingRun
from app.models.video import utc_now
from app.ranking.algorithm import RankingAlgorithm
from app.ranking.repository import RankingRepository
from app.retrieval.fetcher import canonical_url, RetrievalError
from app.retrieval.service import digest
from app.shared.errors import ServiceError

logger = logging.getLogger('verifistream')


def validate_mapping(mapping: MappingRun, video_id: UUID) -> dict:
    retrieval = mapping.retrieval_snapshot
    if (mapping.video_id != video_id or retrieval.status != 'completed'
            or mapping.request.retrieval_run_id != retrieval.id
            or mapping.retrieval_sha256 != digest(retrieval)):
        raise ValueError('Inconsistent mapping lineage')
    pairs = validate_snapshot(retrieval, video_id)
    ids = [r.passage_id for r in mapping.results]
    if (len(ids) != len(set(ids)) or set(ids) != set(mapping.request.passage_ids)
            or not set(ids) <= pairs.keys()):
        raise ValueError('Inconsistent mapping selection')
    failures = 0
    for result in mapping.results:
        proposition, _, passage, source = pairs[result.passage_id]
        if (result.proposition_id != proposition.id or result.source_id != source.id
                or result.citation_url != source.final_url):
            raise ValueError('Inconsistent mapping reference')
        if result.status == 'failed':
            failures += 1
            if (result.decision is not None or result.quote_char_start is not None
                    or result.quote_char_end is not None or not result.error_code):
                raise ValueError('Invalid failed result')
            continue
        if result.decision is None or result.error_code:
            raise ValueError('Missing decision')
        decision = MappingDecision.model_validate(result.decision.model_dump())
        if result.status != decision.status:
            raise ValueError('Inconsistent decision status')
        quote = decision.evidence_quote
        if quote is not None:
            start, end = result.quote_char_start, result.quote_char_end
            if (start is None or end is None or not passage.char_start <= start < end <= passage.char_end
                    or source.text[start:end] != quote):
                raise ValueError('Invalid evidence quote')
        elif result.quote_char_start is not None or result.quote_char_end is not None:
            raise ValueError('Unexpected quote offsets')
        if (proposition.kind == 'causal' and decision.relationship == 'SUPPORTS'
                and decision.causal_basis != 'explicit_causal_evidence'):
            raise ValueError('Invalid causal support')
    expected = 'failed' if failures == len(ids) else 'partial' if failures else 'completed'
    if mapping.status != expected:
        raise ValueError('Inconsistent run status')
    return pairs


def validate_annotations(request: RankingRequest, mapping: MappingRun, pairs: dict) -> None:
    mapped = {r.passage_id: r for r in mapping.results}
    sources = {s.id: s for s in mapping.retrieval_snapshot.sources
               if s.id in {r.source_id for r in mapping.results}}
    if not request.assessments.keys() <= mapped.keys() or not request.origins.keys() <= sources.keys():
        raise ValueError('Annotation references a foreign passage/source')
    for passage_id, annotation in request.assessments.items():
        result = mapped[passage_id]
        _, _, passage, source = pairs[passage_id]
        if result.status != 'mapped' or result.decision.relationship == 'IRRELEVANT':
            raise ValueError('Only ranked passages may have assessments')
        if (not passage.char_start <= annotation.char_start < annotation.char_end <= passage.char_end
                or source.text[annotation.char_start:annotation.char_end] != annotation.quote):
            raise ValueError('Assessment quote must be inside the selected passage')
    for source_id, annotation in request.origins.items():
        source = sources[source_id]
        if (not 0 <= annotation.char_start < annotation.char_end <= len(source.text)
                or source.text[annotation.char_start:annotation.char_end] != annotation.quote):
            raise ValueError('Origin quote must match the saved source')
        canonical_url(annotation.origin_url)  # syntax/public literal validation only; no fetch


class RankingService:
    def __init__(self, videos: VideoRepository, mappings: MappingRepository,
                 repository: RankingRepository, algorithm: RankingAlgorithm):
        self.videos, self.mappings = videos, mappings
        self.repository, self.algorithm = repository, algorithm
        self.capacity = BoundedSemaphore(1)

    def _video(self, video_id: UUID) -> None:
        if self.videos.get(video_id) is None:
            raise ServiceError('video_not_found', 'Video was not found.', 404)

    def create(self, video_id: UUID, request: RankingRequest) -> RankingRun:
        self._video(video_id)
        if not self.capacity.acquire(blocking=False):
            raise ServiceError('ranking_busy', 'Another ranking is running; retry later.', 503)
        try:
            source = self.mappings.get(video_id, request.mapping_run_id)
            if source is None:
                raise ServiceError('mapping_not_found', 'Mapping was not found.', 404)
            if source.id != request.mapping_run_id:
                raise ServiceError('invalid_source_lineage', 'Mapping ID does not match its record.', 409)
            if source.status not in ('completed', 'partial'):
                raise ServiceError('mapping_not_ready', 'Select a completed or partial mapping.', 409)
            source = source.model_copy(deep=True)
            try:
                pairs = validate_mapping(source, video_id)
            except ValueError as exc:
                raise ServiceError('invalid_source_lineage', 'Saved mapping evidence is inconsistent.', 409) from exc
            try:
                validate_annotations(request, source, pairs)
            except (ValueError, RetrievalError) as exc:
                raise ServiceError('invalid_annotation', 'Use selected IDs, exact quotation offsets and public HTTPS origin URLs.', 422) from exc
            run = RankingRun(id=uuid4(), video_id=video_id, request=request.model_copy(deep=True),
                mapping_snapshot=source, mapping_sha256=digest(source),
                ranking_version=self.algorithm.ranking_version, grouping_version=self.algorithm.grouping_version,
                parameters=dict(self.algorithm.parameters), warnings=[
                    'Ordering is not Evidence Confidence or probability of truth.',
                    'Mapped labels are inherited model interpretations; no fresh verification occurs.',
                    'Dependence groups are not counts of independent confirmations.',
                    'Singletons and distinct domains remain unknown in independence.',
                    'Near-duplicate text is heuristic; connected groups may include indirect links.',
                    'Origin declarations and evidence assessments are user-supplied, unverified input.',
                    'Page metadata remains unverified; missing values are not inferred.',
                    'All selected passages remain visible, including contradictory and unranked results.'])
            self.repository.save(run)
            started = time.monotonic()
            logger.info(json.dumps({'event':'ranking_started','run_id':str(run.id)}))
            try:
                run.groups, run.results = self.algorithm.analyze(source, request)
                run.status = 'completed'
            except Exception:
                run.status, run.error_code = 'failed', 'ranking_failed'
                run.groups, run.results = [], []
            run.finished_at = utc_now()
            run.elapsed_seconds = round(time.monotonic()-started, 3)
            self.repository.save(run)
            logger.info(json.dumps({'event':'ranking_finished','run_id':str(run.id),'status':run.status,
                                   'elapsed_seconds':run.elapsed_seconds}))
            return run
        finally:
            self.capacity.release()

    def list(self, video_id: UUID) -> list[RankingRun]:
        self._video(video_id)
        return self.repository.list(video_id)

    def get(self, video_id: UUID, run_id: UUID) -> RankingRun:
        self._video(video_id)
        run = self.repository.get(video_id, run_id)
        if run is None:
            raise ServiceError('ranking_not_found', 'Ranking was not found.', 404)
        return run
