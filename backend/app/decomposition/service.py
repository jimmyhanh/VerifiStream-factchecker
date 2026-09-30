import hashlib
import json
import logging
import re
import time
from threading import BoundedSemaphore
from uuid import UUID, uuid4
from app.claims.repository import ClaimRepository
from app.claims.service import transcript_hash
from app.database.repository import VideoRepository
from app.decomposition.provider import DecompositionProvider, effect, POLICY, ATTRIBUTION, CONTEXT
from app.decomposition.repository import DecompositionRepository
from app.models.claim import ClaimCandidate, ClaimRun
from app.models.proposition import (AtomicProposition, DecompositionPlan, DecompositionRequest,
    DecompositionRun, ParentDecomposition, SourcePart)
from app.models.video import utc_now
from app.shared.config import Settings
from app.shared.errors import ServiceError

logger = logging.getLogger('verifistream')


def snapshot_hash(source: ClaimRun) -> str:
    return hashlib.sha256(json.dumps(source.model_dump(mode='json'), sort_keys=True,
        separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()


def render_plan(candidate: ClaimCandidate, plan: DecompositionPlan, source: ClaimRun) -> ParentDecomposition:
    """Validate source references and render explicit, auditable transformations."""
    plan = DecompositionPlan.model_validate(plan.model_dump())
    quote = candidate.quote
    if plan.review_reason:
        return ParentDecomposition(parent_candidate_id=candidate.id, source_quote=quote,
            status='needs_review',review_reason=plan.review_reason)
    coverage = [False]*len(quote)
    items = []
    previous_predicate_end = -1
    for clause in plan.clauses:
        parts = []
        values = {}
        for role in ('attribution','context','subject','predicate'):
            span = getattr(clause,role)
            if span is None:
                values[role] = None
                continue
            if span.end > len(quote):
                raise ValueError('Source span out of range')
            value = quote[span.start:span.end]
            if not value.strip() or value != value.strip():
                raise ValueError('Blank/untrimmed source fragment')
            if (span.start and quote[span.start-1].isalnum() and value[0].isalnum()
                    or span.end < len(quote) and quote[span.end].isalnum() and value[-1].isalnum()):
                raise ValueError('Source fragment splits a word')
            for index in range(span.start,span.end): coverage[index] = True
            values[role] = value
            parts.append(SourcePart(role=role,char_start=candidate.char_start+span.start,
                char_end=candidate.char_start+span.end,quote=value))
        if clause.subject.end > clause.predicate.start or clause.predicate.start < previous_predicate_end:
            raise ValueError('Invalid subject/predicate ordering')
        previous_predicate_end = clause.predicate.end
        prefix_end = 0
        for role, pattern in [('attribution',ATTRIBUTION),('context',CONTEXT)]:
            span = getattr(clause,role)
            if span:
                if span.start < prefix_end or span.end > clause.subject.start:
                    raise ValueError('Invalid prefix position')
                match = pattern.fullmatch(values[role]+' ')
                if not match:
                    raise ValueError('Unsupported source prefix')
                prefix_end = span.end
        subject, predicate = values['subject'],values['predicate']
        derived = effect(predicate,subject) if clause.separate_effect else None
        if clause.separate_effect and derived is None:
            raise ValueError('Unsupported causal projection')
        causal = bool(re.search(r'\bcaus(?:e|ed|es)\b',predicate,re.I) or
            POLICY.fullmatch(subject) and re.search(r'\b(?:reduce|reduced|increase|increased|create|created)\b',predicate,re.I))
        raw = [(f'{subject} {predicate}', 'causal' if causal else 'factual', 'source_clause')]
        if derived:
            raw.insert(0,(derived[0],'observed_outcome',derived[1]))
        related = []
        for body,kind,transformation in raw:
            prefix = ' '.join(v for v in (values['attribution'],values['context']) if v)
            text = (prefix+' '+body).strip() if prefix else body
            text = text[0].upper()+text[1:]
            if not text.endswith('.'): text += '.'
            segments = []
            cursor = 0
            for segment in source.transcript_snapshot.segments:
                end = cursor+len(segment.text)
                if any(part.char_start < end and part.char_end > cursor for part in parts):
                    segments.append(segment)
                cursor = end+1
            if not segments:
                raise ValueError('No source segments')
            related.append(AtomicProposition(id=uuid4(),parent_candidate_id=candidate.id,text=text,
                kind=kind,transformation=transformation,source_parts=parts,source_quote=quote,
                segment_ids=[seg.id for seg in segments],start_seconds=segments[0].start,
                end_seconds=segments[-1].end, attribution=values['attribution'],context=values['context'],
                needs_context=candidate.needs_context or bool(POLICY.fullmatch(subject)) or bool(re.search(
                    r'\b(?:he|she|it|they|this|that|these|those|last year|today|yesterday)\b',text,re.I))))
        if len(related)==2:
            related[0].related_proposition_ids=[related[1].id]
            related[1].related_proposition_ids=[related[0].id]
        items.extend(related)
    # No lexical content may silently disappear. Only coordination and punctuation
    # may be omitted by normalization; this is not a proof of semantic entailment.
    remaining = ''.join(' ' if used else ch for ch,used in zip(quote,coverage))
    if re.sub(r'\b(?:and|but)\b|[\s.,]', '', remaining, flags=re.I):
        raise ValueError('Uncovered source content')
    return ParentDecomposition(parent_candidate_id=candidate.id,source_quote=quote,
        status='decomposed' if len(items)>1 else 'unchanged',propositions=items)


class DecompositionService:
    def __init__(self,settings: Settings,videos: VideoRepository,claims: ClaimRepository,
                 repository: DecompositionRepository,provider: DecompositionProvider):
        self.settings,self.videos,self.claims = settings,videos,claims
        self.repository,self.provider = repository,provider
        self.capacity = BoundedSemaphore(1)

    def _video(self,video_id: UUID) -> None:
        if self.videos.get(video_id) is None:
            raise ServiceError('video_not_found','Video was not found.',404)

    def create(self,video_id: UUID,request: DecompositionRequest) -> DecompositionRun:
        self._video(video_id)
        if not self.capacity.acquire(blocking=False):
            raise ServiceError('decomposition_busy','Another decomposition is running; retry later.',503)
        try:
            if request.claim_run_id:
                source = self.claims.get(video_id,request.claim_run_id)
                if source is None:
                    raise ServiceError('claim_extraction_not_found','Claim extraction was not found.',404)
            else:
                source = next((r for r in self.claims.list(video_id) if r.status=='completed'),None)
                if source is None:
                    raise ServiceError('claims_not_found','No successful claim extraction exists.',404)
            if source.status!='completed':
                raise ServiceError('claims_not_ready','Select a completed claim extraction.',409)
            source = source.model_copy(deep=True)
            if source.candidates and source.transcript_snapshot.language!='en':
                raise ServiceError('unsupported_decomposition_language','This baseline requires English.',422)
            if len(source.transcript_snapshot.text)>self.settings.max_claim_transcript_chars:
                raise ServiceError('decomposition_input_too_large','Transcript exceeds decomposition input limit.',413)
            ids = {c.id for c in source.candidates}
            if len(ids)!=len(source.candidates):
                raise ServiceError('invalid_claim_lineage','Duplicate source candidate IDs.',409)
            if request.candidate_ids and not set(request.candidate_ids)<=ids:
                raise ServiceError('candidate_not_found','Candidate does not belong to the selected extraction.',404)
            selected = [c for c in source.candidates if request.candidate_ids is None or c.id in request.candidate_ids]
            if len(selected)>100:
                raise ServiceError('too_many_candidates','Select at most 100 candidate IDs per run.',413)
            text = source.transcript_snapshot.text
            if transcript_hash(source.transcript_snapshot)!=source.transcript_sha256 or any(
                c.char_end>len(text) or text[c.char_start:c.char_end]!=c.quote for c in selected):
                raise ServiceError('invalid_claim_lineage','Claim source snapshot or quotation is inconsistent.',409)
            run = DecompositionRun(id=uuid4(),video_id=video_id,claim_run_id=source.id,
                transcript_run_id=source.transcript_run_id,provider=self.provider.info(),
                claim_snapshot_sha256=snapshot_hash(source),claim_snapshot=source,
                selected_candidate_ids=[c.id for c in selected],warnings=[
                    'Experimental English grammar; needs_review parents have no atomic propositions.',
                    'Normalized proposition text may be derived; source_parts contain exact quotations.',
                    'Causal and observed propositions are assertions, not verified findings.',
                    'Missing context is not filled in; time ranges enclose ASR segments.',
                    'Valid source spans do not prove semantic faithfulness. No Evidence Confidence is computed.'])
            self.repository.save(run)
            started = time.monotonic()
            logger.info(json.dumps({'event':'decomposition_started','run_id':str(run.id),'video_id':str(video_id)}))
            try:
                results = [render_plan(c,self.provider.decompose(c.model_copy(deep=True)),source) for c in selected]
                run.results = results
                run.unresolved_count = sum(r.status=='needs_review' for r in results)
                run.proposition_count = sum(len(r.propositions) for r in results)
                run.status = 'completed'
            except (ValueError,TypeError,AttributeError):
                run.status,run.error_code = 'failed','invalid_decomposition_output'
                run.error_message = 'Provider returned an invalid decomposition plan.'
            except Exception:
                run.status,run.error_code = 'failed','decomposition_failed'
                run.error_message = 'Decomposition failed unexpectedly.'
            run.finished_at=utc_now()
            run.elapsed_seconds=round(time.monotonic()-started,3)
            self.repository.save(run)
            logger.info(json.dumps({'event':'decomposition_finished','run_id':str(run.id),
                'status':run.status,'propositions':run.proposition_count,'unresolved':run.unresolved_count,
                'elapsed_seconds':run.elapsed_seconds,'error_code':run.error_code}))
            return run
        finally:
            self.capacity.release()

    def list(self,video_id: UUID) -> list[DecompositionRun]:
        self._video(video_id)
        return self.repository.list(video_id)

    def get(self,video_id: UUID,run_id: UUID) -> DecompositionRun:
        self._video(video_id)
        result = self.repository.get(video_id,run_id)
        if result is None:
            raise ServiceError('decomposition_not_found','Decomposition was not found.',404)
        return result

    def latest(self,video_id: UUID) -> DecompositionRun:
        for run in self.list(video_id):
            if run.status=='completed': return run
        raise ServiceError('propositions_not_found','No successful decomposition exists.',404)
