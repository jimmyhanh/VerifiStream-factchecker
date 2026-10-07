import hashlib
import json
import logging
import time
from threading import BoundedSemaphore
from uuid import UUID, uuid4
from app.database.repository import VideoRepository
from app.decomposition.repository import DecompositionRepository
from app.decomposition.service import snapshot_hash
from app.claims.service import transcript_hash
from app.models.retrieval import (RetrievalRequest, RetrievalRun, PropositionRetrieval,
    SearchHit, FetchAttempt, SourceSnapshot)
from app.models.video import utc_now
from app.retrieval.fetcher import SourceFetcher, RetrievalError, canonical_url
from app.retrieval.passages import PassageExtractor
from app.retrieval.repository import RetrievalRepository
from app.retrieval.search import SearchProvider
from app.shared.errors import ServiceError

logger = logging.getLogger('verifistream')


def digest(model) -> str:
    return hashlib.sha256(json.dumps(model.model_dump(mode='json'), sort_keys=True,
        separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


class RetrievalService:
    def __init__(self, videos: VideoRepository, decompositions: DecompositionRepository,
                 repository: RetrievalRepository, search: SearchProvider,
                 fetcher: SourceFetcher, extractor: PassageExtractor):
        self.videos, self.decompositions, self.repository = videos, decompositions, repository
        self.search, self.fetcher, self.extractor = search, fetcher, extractor
        self.capacity = BoundedSemaphore(1)

    def _video(self, video_id: UUID) -> None:
        if self.videos.get(video_id) is None:
            raise ServiceError('video_not_found', 'Video was not found.', 404)

    def create(self, video_id: UUID, request: RetrievalRequest) -> RetrievalRun:
        self._video(video_id)
        if not self.capacity.acquire(blocking=False):
            raise ServiceError('retrieval_busy', 'Another retrieval is running; retry later.', 503)
        try:
            source = (self.decompositions.get(video_id, request.decomposition_run_id)
                      if request.decomposition_run_id else next(
                          (r for r in self.decompositions.list(video_id) if r.status == 'completed'), None))
            if source is None:
                raise ServiceError('decomposition_not_found', 'No selected completed decomposition exists.', 404)
            if source.status != 'completed':
                raise ServiceError('decomposition_not_ready', 'Select a completed decomposition.', 409)
            source = source.model_copy(deep=True)
            claim = source.claim_snapshot
            if (source.video_id != video_id or claim.video_id != video_id or source.claim_run_id != claim.id
                    or source.transcript_run_id != claim.transcript_run_id
                    or snapshot_hash(claim) != source.claim_snapshot_sha256
                    or transcript_hash(claim.transcript_snapshot) != claim.transcript_sha256):
                raise ServiceError('invalid_source_lineage', 'Source snapshot lineage is inconsistent.', 409)
            propositions = [p for parent in source.results for p in parent.propositions]
            by_id = {p.id: p for p in propositions}
            if len(by_id) != len(propositions):
                raise ServiceError('invalid_source_lineage', 'Duplicate proposition IDs.', 409)
            if not set(request.proposition_ids) <= by_id.keys():
                raise ServiceError('proposition_not_found', 'A proposition does not belong to this decomposition.', 404)
            selected = [by_id[i] for i in request.proposition_ids]
            candidates = {c.id: c for c in claim.candidates}
            text = claim.transcript_snapshot.text
            for proposition in selected:
                candidate = candidates.get(proposition.parent_candidate_id)
                if (candidate is None or proposition.source_quote != candidate.quote
                        or not proposition.source_parts or any(
                            not 0 <= part.char_start < part.char_end <= len(text)
                            or text[part.char_start:part.char_end] != part.quote
                            for part in proposition.source_parts)):
                    raise ServiceError('invalid_source_lineage', 'Proposition quotation is inconsistent.', 409)
            run = RetrievalRun(id=uuid4(), video_id=video_id, decomposition_run_id=source.id,
                decomposition_snapshot=source, decomposition_sha256=digest(source), request=request.model_copy(deep=True),
                discovery_provider=self.search.name if request.mode == 'search' else 'manual-urls-v1',
                parameters={'max_results_per_proposition': 5, 'max_passages_per_source': 3,
                    'max_passage_chars': 1000, 'run_budget_seconds': 90,
                    'source_fetcher': type(self.fetcher).__name__, 'extractor': type(self.extractor).__name__},
                warnings=['Retrieved passages are candidates, not support/contradiction judgments.',
                    'Lexical relevance is not Evidence Confidence or semantic entailment.',
                    'Page-declared metadata is unverified; unknown dates/types/independence stay unknown.',
                    'User context is unverified search input and does not amend the original assertion.',
                    'Different domains do not imply independent corroboration.',
                    'completed means processing finished; inspect individual results and errors.'])
            self.repository.save(run)
            started = time.monotonic()
            logger.info(json.dumps({'event': 'retrieval_started', 'run_id': str(run.id)}))
            cache: dict[str, SourceSnapshot] = {}
            hashes: dict[str, UUID] = {}
            try:
                for proposition in selected:
                    context = request.contexts.get(proposition.id)
                    query = proposition.text + (' ' + context.strip() if context else '')
                    result = PropositionRetrieval(proposition_id=proposition.id, query=query,
                        user_context=context, context_origin='user_supplied' if context else None, status='no_passages')
                    run.results.append(result)
                    if proposition.needs_context and not context:
                        result.status, result.error_code = 'needs_context', 'context_required'
                        continue
                    if len(query) > 600 or len(query.split()) > 75:
                        result.status, result.error_code = 'failed', 'query_too_long'
                        continue
                    try:
                        if time.monotonic() - started >= 90:
                            raise RetrievalError('run_budget_exceeded')
                        hits = ([SearchHit(url=url) for url in request.source_urls[proposition.id]]
                                if request.mode == 'manual_urls' else self.search.search(query, 5))
                        result.hits = [SearchHit.model_validate(h.model_dump()) for h in hits[:5]]
                    except RetrievalError as exc:
                        result.status, result.error_code = 'failed', exc.code
                        continue
                    except Exception:
                        result.status, result.error_code = 'failed', 'search_failed'
                        continue
                    used_ids: set[UUID] = set()
                    for hit in result.hits:
                        try:
                            if time.monotonic() - started >= 90:
                                raise RetrievalError('run_budget_exceeded')
                            url = canonical_url(hit.url)
                            cached = url in cache
                            if cached:
                                snapshot = cache[url]
                            else:
                                page = self.fetcher.fetch(url)
                                snapshot = self.extractor.snapshot(url, page)
                                canonical_url(snapshot.final_url)
                                if hashlib.sha256(snapshot.text.encode()).hexdigest() != snapshot.text_sha256:
                                    raise RetrievalError('invalid_source_snapshot')
                                snapshot.duplicate_of_source_id = hashes.get(snapshot.text_sha256)
                                hashes.setdefault(snapshot.text_sha256, snapshot.id)
                                run.sources.append(snapshot)
                                cache[url] = snapshot
                                cache.setdefault(canonical_url(snapshot.final_url), snapshot)
                            result.attempts.append(FetchAttempt(url=hit.url,
                                status='duplicate_url' if cached else 'fetched', source_id=snapshot.id))
                            if snapshot.id not in used_ids:
                                passages = self.extractor.passages(snapshot, query)
                                for passage in passages:
                                    if (passage.source_id != snapshot.id or
                                            not 0 <= passage.char_start < passage.char_end <= len(snapshot.text) or
                                            snapshot.text[passage.char_start:passage.char_end] != passage.text):
                                        raise RetrievalError('invalid_passage')
                                result.passages.extend(passages)
                                used_ids.add(snapshot.id)
                        except RetrievalError as exc:
                            result.attempts.append(FetchAttempt(url=hit.url, status='failed', error_code=exc.code))
                        except Exception:
                            result.attempts.append(FetchAttempt(url=hit.url, status='failed', error_code='source_processing_failed'))
                    failures = any(a.status == 'failed' for a in result.attempts)
                    successes = any(a.source_id for a in result.attempts)
                    result.status = ('partial' if failures else 'retrieved') if result.passages else (
                        'partial' if failures and successes else 'failed' if failures else 'no_passages')
                run.status = 'failed' if all(r.status == 'failed' for r in run.results) else 'completed'
                if run.status == 'failed': run.error_code = 'all_retrievals_failed'
            except Exception:
                run.status, run.error_code = 'failed', 'retrieval_failed'
            run.finished_at = utc_now()
            run.elapsed_seconds = round(time.monotonic() - started, 3)
            self.repository.save(run)
            logger.info(json.dumps({'event': 'retrieval_finished', 'run_id': str(run.id),
                'status': run.status, 'sources': len(run.sources), 'elapsed_seconds': run.elapsed_seconds}))
            return run
        finally:
            self.capacity.release()

    def list(self, video_id: UUID) -> list[RetrievalRun]:
        self._video(video_id)
        return self.repository.list(video_id)

    def get(self, video_id: UUID, run_id: UUID) -> RetrievalRun:
        self._video(video_id)
        run = self.repository.get(video_id, run_id)
        if run is None:
            raise ServiceError('retrieval_not_found', 'Retrieval was not found.', 404)
        return run
