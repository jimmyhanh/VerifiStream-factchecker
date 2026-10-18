import hashlib
import json
import logging
import time
from threading import BoundedSemaphore
from uuid import UUID, uuid4
from app.database.repository import VideoRepository
from app.claims.service import transcript_hash
from app.decomposition.service import snapshot_hash
from app.evidence.provider import MappingProvider, MappingError
from app.evidence.repository import MappingRepository
from app.models.mapping import MappingRequest, MappingRun, MappingResult, MappingDecision
from app.models.proposition import AtomicProposition
from app.models.retrieval import RetrievalRun, PropositionRetrieval, EvidencePassage, SourceSnapshot
from app.models.video import utc_now
from app.retrieval.repository import RetrievalRepository
from app.retrieval.service import digest
from app.shared.errors import ServiceError

logger = logging.getLogger('verifistream')


def validate_snapshot(run: RetrievalRun, video_id: UUID) -> dict:
    """Revalidate stored lineage and exact evidence before any provider call."""
    decomposition = run.decomposition_snapshot
    claim = decomposition.claim_snapshot
    if (run.video_id != video_id or decomposition.video_id != video_id
            or claim.video_id != video_id or claim.status != 'completed' or decomposition.status != 'completed'
            or run.decomposition_run_id != decomposition.id
            or run.decomposition_sha256 != digest(decomposition)
            or decomposition.claim_run_id != claim.id
            or decomposition.transcript_run_id != claim.transcript_run_id
            or decomposition.claim_snapshot_sha256 != snapshot_hash(claim)
            or claim.transcript_sha256 != transcript_hash(claim.transcript_snapshot)):
        raise ValueError('Invalid lineage')
    propositions = [p for parent in decomposition.results for p in parent.propositions]
    by_id = {p.id: p for p in propositions}
    sources = {s.id: s for s in run.sources}
    candidates = {c.id: c for c in claim.candidates}
    if len(by_id) != len(propositions) or len(sources) != len(run.sources):
        raise ValueError('Duplicate IDs')
    if {r.proposition_id for r in run.results} != set(run.request.proposition_ids):
        raise ValueError('Inconsistent selection')
    if len(run.results) != len(run.request.proposition_ids):
        raise ValueError('Duplicate result')
    for source in run.sources:
        if hashlib.sha256(source.text.encode()).hexdigest() != source.text_sha256:
            raise ValueError('Invalid source digest')
    pairs = {}
    transcript = claim.transcript_snapshot.text
    for result in run.results:
        proposition = by_id.get(result.proposition_id)
        if proposition is None:
            raise ValueError('Unknown proposition')
        candidate = candidates.get(proposition.parent_candidate_id)
        if (candidate is None or candidate.quote != proposition.source_quote or not proposition.source_parts
                or any(not 0 <= part.char_start < part.char_end <= len(transcript)
                       or transcript[part.char_start:part.char_end] != part.quote
                       for part in proposition.source_parts)):
            raise ValueError('Invalid proposition quote')
        if result.user_context != run.request.contexts.get(proposition.id):
            raise ValueError('Inconsistent context')
        for passage in result.passages:
            source = sources.get(passage.source_id)
            if (passage.id in pairs or source is None
                    or result.status not in ('retrieved', 'partial')
                    or not 0 <= passage.char_start < passage.char_end <= len(source.text)
                    or source.text[passage.char_start:passage.char_end] != passage.text
                    or len(passage.text) > 1000):
                raise ValueError('Invalid passage')
            pairs[passage.id] = (proposition, result, passage, source)
    return pairs


def provider_payload(proposition: AtomicProposition, result: PropositionRetrieval,
                     passage: EvidencePassage, source: SourceSnapshot) -> dict:
    return {'proposition': {'text': proposition.text, 'kind': proposition.kind,
                'source_quote': proposition.source_quote, 'attribution': proposition.attribution,
                'context': proposition.context, 'needs_context': proposition.needs_context},
            'unverified_user_search_context': result.user_context,
            'passage': passage.text,
            'unverified_source_metadata': {'title': source.title,
                'publisher': source.publisher, 'publication_date': source.publication_date}}


class MappingService:
    def __init__(self, videos: VideoRepository, retrievals: RetrievalRepository,
                 repository: MappingRepository, provider: MappingProvider):
        self.videos, self.retrievals = videos, retrievals
        self.repository, self.provider = repository, provider
        self.capacity = BoundedSemaphore(1)

    def _video(self, video_id: UUID) -> None:
        if self.videos.get(video_id) is None:
            raise ServiceError('video_not_found', 'Video was not found.', 404)

    def create(self, video_id: UUID, request: MappingRequest) -> MappingRun:
        self._video(video_id)
        if not self.capacity.acquire(blocking=False):
            raise ServiceError('mapping_busy', 'Another mapping is running; retry later.', 503)
        try:
            source = self.retrievals.get(video_id, request.retrieval_run_id)
            if source is None:
                raise ServiceError('retrieval_not_found', 'Retrieval was not found.', 404)
            if source.status != 'completed':
                raise ServiceError('retrieval_not_ready', 'Select a completed retrieval.', 409)
            source = source.model_copy(deep=True)
            try:
                pairs = validate_snapshot(source, video_id)
            except ValueError as exc:
                raise ServiceError('invalid_source_lineage', 'Saved evidence is inconsistent.', 409) from exc
            if not set(request.passage_ids) <= pairs.keys():
                raise ServiceError('passage_not_found', 'A selected passage does not belong to this retrieval.', 404)
            run = MappingRun(id=uuid4(), video_id=video_id, request=request.model_copy(deep=True),
                retrieval_snapshot=source, retrieval_sha256=digest(source),
                provider=self.provider.name, requested_model=self.provider.model,
                prompt_version=self.provider.prompt_version, prompt_snapshot=self.provider.prompt,
                parameters={**self.provider.parameters, 'max_passages': 12, 'run_budget_seconds': 180},
                warnings=['Relationships are model interpretations of passages, not fact-check verdicts.',
                    'Exact quotations validate provenance, not semantic correctness.',
                    'Page metadata and user search context remain unverified.',
                    'completed means all selected pairs were processed; inspect needs_review results.',
                    'No Evidence Confidence, source independence or aggregate verdict is computed.'])
            self.repository.save(run)
            started = time.monotonic()
            logger.info(json.dumps({'event': 'mapping_started', 'run_id': str(run.id)}))
            for passage_id in request.passage_ids:
                proposition, retrieval_result, passage, snapshot = pairs[passage_id]
                result = MappingResult(proposition_id=proposition.id, passage_id=passage.id,
                    source_id=snapshot.id, status='failed', citation_url=snapshot.final_url)
                run.results.append(result)
                try:
                    if time.monotonic() - started >= 180:
                        raise MappingError('mapping_budget_exceeded')
                    if proposition.needs_context and not retrieval_result.user_context:
                        raise MappingError('mapping_context_required')
                    payload = provider_payload(proposition, retrieval_result, passage, snapshot)
                    if len(json.dumps(payload, ensure_ascii=False)) > 16000:
                        raise MappingError('mapping_input_too_large')
                    reply = self.provider.map(payload)
                    # Validate injected adapters too; don't trust model_construct/mutable objects.
                    decision = MappingDecision.model_validate(reply.decision.model_dump())
                    result.returned_model, result.provider_response_id = reply.model, reply.response_id
                    result.usage = reply.usage
                    if decision.evidence_quote is not None:
                        quote = decision.evidence_quote
                        if not quote.strip() or quote not in passage.text:
                            raise MappingError('invalid_evidence_quote')
                        offset = passage.text.index(quote)
                        result.quote_char_start = passage.char_start + offset
                        result.quote_char_end = result.quote_char_start + len(quote)
                    if (proposition.kind == 'causal' and decision.relationship == 'SUPPORTS'
                            and decision.causal_basis != 'explicit_causal_evidence'):
                        # Reject a provider's inconsistent causal support rather than invent a label.
                        raise MappingError('unsupported_causal_mapping')
                    result.decision, result.status = decision, decision.status
                except MappingError as exc:
                    result.error_code = exc.code
                    result.quote_char_start = result.quote_char_end = None
                except Exception:
                    result.error_code = 'mapping_provider_failed'
                    result.quote_char_start = result.quote_char_end = None
            failures = sum(r.status == 'failed' for r in run.results)
            run.status = 'failed' if failures == len(run.results) else 'partial' if failures else 'completed'
            run.finished_at = utc_now()
            run.elapsed_seconds = round(time.monotonic() - started, 3)
            self.repository.save(run)
            logger.info(json.dumps({'event': 'mapping_finished', 'run_id': str(run.id),
                                   'status': run.status, 'elapsed_seconds': run.elapsed_seconds}))
            return run
        finally:
            self.capacity.release()

    def list(self, video_id: UUID) -> list[MappingRun]:
        self._video(video_id)
        return self.repository.list(video_id)

    def get(self, video_id: UUID, run_id: UUID) -> MappingRun:
        self._video(video_id)
        run = self.repository.get(video_id, run_id)
        if run is None:
            raise ServiceError('mapping_not_found', 'Mapping was not found.', 404)
        return run
