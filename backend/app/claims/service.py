import hashlib
import json
import logging
import re
import time
from threading import BoundedSemaphore
from uuid import UUID, uuid4
from app.claims.provider import ClaimProvider
from app.claims.repository import ClaimRepository
from app.database.repository import VideoRepository
from app.models.claim import ClaimCandidate, ClaimRequest, ClaimRun, ClaimSpan
from app.models.transcript import TranscriptResult
from app.models.video import utc_now
from app.shared.config import Settings
from app.shared.errors import ServiceError
from app.transcription.repository import TranscriptRepository

logger = logging.getLogger('verifistream')
_REASONS = {'numerical': 'Contains a numerical assertion',
            'causal': 'Asserts a cause or explanation',
            'factual_event': 'Describes an event, change, or observable relationship'}
_CONTEXT = re.compile(r'\b(?:he|she|it|they|this|that|these|those|here|there|last year|last month|today|yesterday)\b', re.I)


def transcript_hash(snapshot: TranscriptResult) -> str:
    payload = json.dumps(snapshot.model_dump(mode='json'), sort_keys=True,
                         separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def grounded_candidates(snapshot: TranscriptResult, spans: list[ClaimSpan]) -> list[ClaimCandidate]:
    """Derive all quotation, segment and time fields from source, never provider text."""
    text = snapshot.text
    intervals = []
    offset = 0
    for segment in snapshot.segments:
        intervals.append((offset, offset + len(segment.text), segment))
        offset += len(segment.text) + 1
    candidates = []
    previous_end = 0
    if len(spans) > 1000:
        raise ValueError('Too many candidate spans')
    for raw in spans:
        span = ClaimSpan.model_validate(raw.model_dump())
        if span.char_start < previous_end or span.char_end > len(text):
            raise ValueError('Unordered, overlapping or out-of-range span')
        quote = text[span.char_start:span.char_end]
        if not quote.strip() or quote != quote.strip():
            raise ValueError('Blank or untrimmed quote')
        # Reject spans that split a word, including fabricated partial tokens.
        if (span.char_start and text[span.char_start-1].isalnum() and quote[0].isalnum()
                or span.char_end < len(text) and text[span.char_end].isalnum() and quote[-1].isalnum()):
            raise ValueError('Span splits a word')
        covered = [seg for start, end, seg in intervals
                   if start < span.char_end and end > span.char_start]
        if not covered:
            raise ValueError('Span has no source segments')
        candidates.append(ClaimCandidate(**span.model_dump(), id=uuid4(), quote=quote,
            segment_ids=[seg.id for seg in covered], start_seconds=covered[0].start,
            end_seconds=covered[-1].end,
            reason='; '.join(_REASONS[signal] for signal in span.signals) + '. Not fact-checked.',
            needs_context=bool(_CONTEXT.search(quote))))
        previous_end = span.char_end
    return candidates


class ClaimService:
    def __init__(self, settings: Settings, videos: VideoRepository,
                 transcripts: TranscriptRepository, repository: ClaimRepository,
                 provider: ClaimProvider):
        self.settings = settings
        self.videos = videos
        self.transcripts = transcripts
        self.repository = repository
        self.provider = provider
        self.capacity = BoundedSemaphore(1)

    def _video(self, video_id: UUID) -> None:
        if self.videos.get(video_id) is None:
            raise ServiceError('video_not_found', 'Video was not found.', 404)

    def create(self, video_id: UUID, request: ClaimRequest) -> ClaimRun:
        self._video(video_id)
        if not self.capacity.acquire(blocking=False):
            raise ServiceError('claim_extraction_busy', 'Another extraction is running; retry later.', 503)
        try:
            if request.transcript_run_id is not None:
                source = self.transcripts.get(video_id, request.transcript_run_id)
                if source is None:
                    raise ServiceError('transcription_not_found', 'Transcription run was not found.', 404)
            else:
                source = next((r for r in self.transcripts.list(video_id) if r.status == 'completed'), None)
                if source is None:
                    raise ServiceError('transcript_not_found', 'No successful transcript exists.', 404)
            if source.status != 'completed' or source.result is None:
                raise ServiceError('transcript_not_ready', 'Select a completed transcript.', 409)
            snapshot = source.result.model_copy(deep=True)
            if snapshot.segments and snapshot.language != 'en':
                raise ServiceError('unsupported_claim_language', 'This baseline requires an English transcript.', 422)
            if len(snapshot.text) > self.settings.max_claim_transcript_chars:
                raise ServiceError('claim_input_too_large', 'Transcript exceeds claim extraction limit.', 413)
            run = ClaimRun(id=uuid4(), video_id=video_id, transcript_run_id=source.id,
                transcript_snapshot=snapshot, transcript_sha256=transcript_hash(snapshot),
                provider=self.provider.info(), warnings=[
                    'Experimental English rules can miss claims and select non-claims.',
                    'Candidates are not verified. No Evidence Confidence is calculated.',
                    'Times enclose source ASR segments; they are not word-aligned.',
                    'needs_context is a heuristic; false does not guarantee complete context.'])
            self.repository.save(run)
            started = time.monotonic()
            logger.info(json.dumps({'event': 'claim_extraction_started', 'run_id': str(run.id),
                                    'video_id': str(video_id)}))
            try:
                spans = self.provider.extract(snapshot.model_copy(deep=True))
                run.candidates = grounded_candidates(snapshot, spans)
                run.status = 'completed'
            except (ValueError, TypeError, AttributeError):
                run.status = 'failed'
                run.error_code = 'invalid_claim_output'
                run.error_message = 'Claim provider returned invalid source spans.'
            except Exception:
                run.status = 'failed'
                run.error_code = 'claim_extraction_failed'
                run.error_message = 'Claim extraction failed unexpectedly.'
            run.finished_at = utc_now()
            run.elapsed_seconds = round(time.monotonic() - started, 3)
            self.repository.save(run)
            logger.info(json.dumps({'event': 'claim_extraction_finished', 'run_id': str(run.id),
                'status': run.status, 'candidate_count': len(run.candidates),
                'elapsed_seconds': run.elapsed_seconds, 'error_code': run.error_code}))
            return run
        finally:
            self.capacity.release()

    def list(self, video_id: UUID) -> list[ClaimRun]:
        self._video(video_id)
        return self.repository.list(video_id)

    def get(self, video_id: UUID, run_id: UUID) -> ClaimRun:
        self._video(video_id)
        run = self.repository.get(video_id, run_id)
        if run is None:
            raise ServiceError('claim_extraction_not_found', 'Claim extraction was not found.', 404)
        return run

    def latest(self, video_id: UUID) -> ClaimRun:
        for run in self.list(video_id):
            if run.status == 'completed':
                return run
        raise ServiceError('claims_not_found', 'No successful claim extraction exists.', 404)
