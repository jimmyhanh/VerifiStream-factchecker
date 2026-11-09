from contextlib import asynccontextmanager
import hashlib
from pydantic import ValidationError, BaseModel
from app.jobs.service import LocalJobs, Job, JobRequest
from app.publishers.registry import PublisherRegistry
import json
from uuid import UUID, uuid4
from fastapi import FastAPI, Request, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from app.api.limits import UploadLimits
from app.database.repository import JsonVideoRepository, VideoRepository
from app.media.ffmpeg import FFmpegProcessor, MediaProcessor
from app.models.video import HealthResponse, VideoRecord, VideoStatus, PublicConfiguration
from app.shared.config import Settings
from app.shared.errors import ServiceError
from app.storage.local import LocalVideoStorage, VideoStorage
from app.videos.service import VideoService
from app.models.transcript import TranscriptRequest, TranscriptRun
from app.transcription.provider import TranscriptionProvider, FasterWhisperProvider
from app.transcription.repository import TranscriptRepository, JsonTranscriptRepository
from app.transcription.service import TranscriptionService

from app.claims.provider import ClaimProvider, EnglishRuleClaimProvider
from app.claims.repository import ClaimRepository, JsonClaimRepository
from app.claims.service import ClaimService
from app.models.claim import ClaimRequest, ClaimRun
from app.decomposition.provider import DecompositionProvider, EnglishRuleDecompositionProvider
from app.decomposition.repository import DecompositionRepository, JsonDecompositionRepository
from app.decomposition.service import DecompositionService
from app.models.proposition import DecompositionRequest, DecompositionRun

from app.models.retrieval import RetrievalRequest, RetrievalRun
from app.retrieval.repository import RetrievalRepository, JsonRetrievalRepository
from app.retrieval.search import SearchProvider, BraveSearchProvider
from app.retrieval.fetcher import SourceFetcher, PublicHTTPSFetcher
from app.retrieval.passages import PassageExtractor, LexicalPassageExtractor
from app.retrieval.service import RetrievalService


from app.models.mapping import MappingRequest, MappingRun
from app.evidence.provider import MappingProvider, OpenAIMappingProvider
from app.evidence.repository import MappingRepository, JsonMappingRepository
from app.evidence.service import MappingService


from app.models.ranking import RankingRequest, RankingRun
from app.ranking.algorithm import RankingAlgorithm, TransparentRankingAlgorithm
from app.ranking.repository import RankingRepository, JsonRankingRepository
from app.ranking.service import RankingService


from app.models.verification import VerificationRequest, VerificationRun
from app.verification.policy import VerificationPolicy, SelectedEvidencePolicy
from app.verification.repository import VerificationRepository, JsonVerificationRepository
from app.verification.service import VerificationService
from app.models.confidence import ConfidenceRequest, ConfidenceRun
from app.confidence.algorithm import ConfidenceAlgorithm, TransparentConfidenceAlgorithm
from app.confidence.repository import ConfidenceRepository, JsonConfidenceRepository
from app.confidence.service import ConfidenceService
from app.models.review import DraftRequest, DraftRun, ReviewRequest
from app.review.provider import SuggestionProvider, OpenAISuggestionProvider
from app.review.repository import JsonDraftRepository
from app.review.service import ReviewService
from app.videos.deletion import (VideoActivity, VideoActivityMiddleware, VideoDeletionService,
    ClearVideosRequest, DeletionPreview, DeletionResult)


def create_app(
    settings: Settings | None = None, *,
    storage: VideoStorage | None = None,
    repository: VideoRepository | None = None,
    media: MediaProcessor | None = None,
    transcription_provider: TranscriptionProvider | None = None,
    transcript_repository: TranscriptRepository | None = None,
    claim_provider: ClaimProvider | None = None,
    claim_repository: ClaimRepository | None = None,
    decomposition_provider: DecompositionProvider | None = None,
    decomposition_repository: DecompositionRepository | None = None,
    search_provider: SearchProvider | None = None,
    source_fetcher: SourceFetcher | None = None,
    passage_extractor: PassageExtractor | None = None,
    retrieval_repository: RetrievalRepository | None = None,
    mapping_provider: MappingProvider | None = None,
    mapping_repository: MappingRepository | None = None,
    ranking_repository: RankingRepository | None = None,
    ranking_algorithm: RankingAlgorithm | None = None,
    verification_repository: VerificationRepository | None = None,
    verification_policy: VerificationPolicy | None = None,
    confidence_repository: ConfidenceRepository | None = None,
    confidence_algorithm: ConfidenceAlgorithm | None = None,
    suggestion_provider: SuggestionProvider | None = None,
) -> FastAPI:
    config = settings or Settings.from_env()
    publisher_registry = PublisherRegistry(config.publisher_ratings_file)
    video_storage = storage or LocalVideoStorage(config.storage_root)
    video_repository = repository or JsonVideoRepository(config.storage_root)
    transcripts = transcript_repository or JsonTranscriptRepository(config.storage_root)
    claim_records = claim_repository or JsonClaimRepository(config.storage_root)
    decomposition_records = decomposition_repository or JsonDecompositionRepository(config.storage_root)
    retrieval_records = retrieval_repository or JsonRetrievalRepository(config.storage_root)
    activity = VideoActivity()
    deletion = VideoDeletionService(video_repository, video_storage, activity)
    review = ReviewService(video_repository, claim_records, JsonDraftRepository(config.storage_root),
        decomposition_records, suggestion_provider or OpenAISuggestionProvider(
            config.openai_api_key.get_secret_value(), config.decomposition_model or config.mapping_model))
    mapping_records = mapping_repository or JsonMappingRepository(config.storage_root)
    ranking_records = ranking_repository or JsonRankingRepository(config.storage_root)
    verification_records = verification_repository or JsonVerificationRepository(config.storage_root)
    confidence = ConfidenceService(video_repository, verification_records,
        confidence_repository or JsonConfidenceRepository(config.storage_root),
        confidence_algorithm or TransparentConfidenceAlgorithm())
    verification = VerificationService(video_repository, ranking_records,
        verification_records,
        verification_policy or SelectedEvidencePolicy(),
        rating_snapshot=lambda run: publisher_registry.snapshot(config.storage_root, run))
    ranking = RankingService(video_repository, mapping_records,
        ranking_records,
        ranking_algorithm or TransparentRankingAlgorithm())
    mapping = MappingService(video_repository, retrieval_records,
        mapping_records,
        mapping_provider or OpenAIMappingProvider(config.openai_api_key.get_secret_value(), config.mapping_model))
    retrieval = RetrievalService(video_repository, decomposition_records,
        retrieval_records,
        search_provider or BraveSearchProvider(config.brave_search_api_key.get_secret_value()),
        source_fetcher or PublicHTTPSFetcher(), passage_extractor or LexicalPassageExtractor())
    decomposition = DecompositionService(config, video_repository, claim_records,
        decomposition_records,
        decomposition_provider or EnglishRuleDecompositionProvider())
    claims = ClaimService(config, video_repository, transcripts,
                          claim_records,
                          claim_provider or EnglishRuleClaimProvider())
    transcription = TranscriptionService(
        config, video_repository, video_storage,
        transcripts,
        transcription_provider or FasterWhisperProvider(config),
    )
    service = VideoService(
        config, video_storage, video_repository,
        media or FFmpegProcessor(config),
    )
    adapters = {
        'transcript': (TranscriptRequest, transcription),
        'claims': (ClaimRequest, claims), 'atoms': (DecompositionRequest, decomposition),
        'retrieval': (RetrievalRequest, retrieval), 'mapping': (MappingRequest, mapping),
        'ranking': (RankingRequest, ranking), 'verification': (VerificationRequest, verification),
        'confidence': (ConfidenceRequest, confidence),
    }
    def validate_job(video_id, request):
        video = service.get(video_id)
        if request.action == "extract_audio":
            if not video.background_audio or request.input:
                raise ServiceError("invalid_audio_job", "Expected a background upload and empty input.", 422)
            return
        if request.action in ("analyze", "transcript") and video.status != VideoStatus.completed:
            raise ServiceError("audio_not_ready", "Wait for audio extraction before transcribing.", 409)
        action = 'transcript' if request.action == 'analyze' else 'ranking' if request.action == 'findings' else request.action
        try:
            parsed = adapters[action][0].model_validate(request.input)
        except ValidationError:
            raise ServiceError('invalid_job_input', 'Job input does not match the selected action.', 422)
        required = {'claims':'transcript_run_id','atoms':'claim_run_id','retrieval':'decomposition_run_id'}
        if action in required and getattr(parsed, required[action]) is None:
            raise ServiceError('explicit_parent_required','Background jobs require an explicit parent run ID.',422)

    def execute_job(job, checkpoint):
        def step(action, payload):
            schema, adapter = adapters[action]
            if action == "transcript":
                payload = {"reuse_completed": True, **payload}
            if action in job.outputs:
                run = adapter.get(job.video_id, job.outputs[action])
                if run.status not in ('completed','partial'):
                    raise ServiceError('invalid_checkpoint','Saved checkpoint is not complete.',409)
            else:
                checkpoint(job, action)
                run = adapter.create(job.video_id, schema.model_validate(payload))
                if run.status not in ('completed','partial'):
                    raise ServiceError('job_stage_failed', 'Stage failed; inspect its saved run before retrying.', 422)
                checkpoint(job, action, run.id)
            return run
        if job.request.action == "extract_audio":
            checkpoint(job, "extract_audio")
            record = service.get(job.video_id)
            if record.status != VideoStatus.completed:
                record = service.extract_audio(record)
            if record.status == VideoStatus.failed:
                raise ServiceError(record.error_code, record.error_message)
            return
        if job.request.action == 'analyze':
            transcript = step('transcript', job.request.input)
            claim = step('claims', {'transcript_run_id': transcript.id})
            step('atoms', {'claim_run_id': claim.id})
            checkpoint(job, 'review_claims')
        elif job.request.action == 'findings':
            ranked = step('ranking', job.request.input)
            verified = step('verification', {'ranking_run_id':ranked.id})
            step('confidence', {'verification_run_id':verified.id})
        else:
            step(job.request.action, job.request.input)

    # Non-secret configuration identity prevents checkpoint reuse after model/config changes.
    identity = hashlib.sha256(('jobs-v1:' + config.model_dump_json(exclude={'openai_api_key','brave_search_api_key'})).encode()).hexdigest()
    jobs = LocalJobs(config.storage_root, activity, execute_job, validate_job, identity)
    @asynccontextmanager
    async def lifespan(application):
        jobs.start()
        try: yield
        finally: await run_in_threadpool(jobs.close)
    app = FastAPI(title="VerifiStream", version="0.1.0", lifespan=lifespan)
    app.state.jobs = jobs

    app.add_middleware(
        UploadLimits, max_bytes=config.max_video_bytes + 64 * 1024,
        slots=config.max_concurrent_uploads,
    )

    app.add_middleware(VideoActivityMiddleware, activity=activity)
    app.add_middleware(CORSMiddleware, allow_origins=config.cors_origins,
                       allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"],
                       allow_credentials=False)

    @app.exception_handler(ServiceError)
    async def service_error(request: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(
            {"detail": {"code": exc.code, "message": exc.message}},
            status_code=exc.status_code,
        )

    @app.exception_handler(OSError)
    async def storage_error(request: Request, exc: OSError) -> JSONResponse:
        return JSONResponse(
            {"detail": {"code": "storage_error", "message": "Storage operation failed."}},
            status_code=503,
        )

    @app.get('/publisher-ratings')
    def publisher_rating(url: str = Query(max_length=2048)):
        try: return publisher_registry.lookup(url)
        except ValueError: raise ServiceError('invalid_source_url','Use an HTTP(S) publisher URL without credentials.',422)

    @app.get('/videos/{video_id}/verifications/{run_id}/publisher-ratings')
    def publisher_snapshot(video_id: UUID, run_id: UUID):
        run = verification.get(video_id, run_id)
        path = config.storage_root / str(video_id) / 'publisher-rating-snapshots' / f'{run_id}.json'
        if not path.exists():
            raise ServiceError('rating_snapshot_unavailable','No publisher-rating snapshot was captured for this verification.',404)
        snapshot = json.loads(path.read_text())
        if snapshot['verification_sha256'] != hashlib.sha256(run.model_dump_json().encode()).hexdigest():
            raise ServiceError('rating_snapshot_mismatch','Rating snapshot does not match this verification.',409)
        return snapshot

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """Liveness only; does not guarantee storage/media-tool readiness."""
        return HealthResponse()

    @app.get("/configuration", response_model=PublicConfiguration)
    def public_configuration() -> PublicConfiguration:
        return PublicConfiguration(max_video_bytes=config.max_video_bytes,
                                   max_duration_seconds=config.max_duration_seconds)

    @app.get('/videos/deletion-preview', response_model=DeletionPreview)
    def deletion_preview() -> DeletionPreview:
        return deletion.preview()

    @app.delete('/videos', response_model=DeletionResult)
    def clear_videos(request: ClearVideosRequest) -> DeletionResult:
        return deletion.clear(request)

    @app.delete('/videos/{video_id}', response_model=DeletionResult)
    def delete_video(video_id: UUID) -> DeletionResult:
        return deletion.delete(video_id)

    @app.post('/videos/{video_id}/proposition-drafts', response_model=DraftRun, status_code=201)
    def suggest_propositions(video_id: UUID, request: DraftRequest) -> DraftRun:
        return review.suggest(video_id, request)

    @app.get('/videos/{video_id}/proposition-drafts', response_model=list[DraftRun])
    def list_proposition_drafts(video_id: UUID) -> list[DraftRun]:
        return review.list(video_id)

    @app.get('/videos/{video_id}/proposition-drafts/{run_id}', response_model=DraftRun)
    def get_proposition_draft(video_id: UUID, run_id: UUID) -> DraftRun:
        return review.get(video_id, run_id)

    @app.post('/videos/{video_id}/reviewed-decompositions', response_model=DecompositionRun, status_code=201)
    def approve_propositions(video_id: UUID, request: ReviewRequest) -> DecompositionRun:
        return review.approve(video_id, request)

    def audio_status(record: VideoRecord) -> VideoRecord:
        if not record.background_audio or record.status == VideoStatus.completed:
            return record
        job = jobs.latest_audio(record.id)
        if job and job.status == "completed":
            return service.get(record.id)
        if job and job.status in ("queued", "running"):
            return record.model_copy(update={"status": VideoStatus.queued if job.status == "queued"
                else VideoStatus.processing, "error_code": None, "error_message": None})
        if record.status != VideoStatus.failed or not job or job.status != "failed":
            code = (job.error_code or job.status) if job else "audio_job_missing"
            return record.model_copy(update={"status": VideoStatus.failed, "error_code": code,
                "error_message": f"Audio extraction did not finish ({code})."})
        return record

    def enqueue_upload(stream, filename, content_type) -> VideoRecord:
        record = service.store_upload(stream, filename, content_type, background=True)
        try:
            jobs.submit(record.id, JobRequest(key=uuid4(), action="extract_audio"))
        except Exception:
            video_storage.remove(record.id)
            raise
        return record

    @app.get("/videos", response_model=list[VideoRecord])
    def list_videos(limit: int = Query(default=50, ge=1, le=100),
                    offset: int = Query(default=0, ge=0)) -> list[VideoRecord]:
        return [audio_status(record) for record in video_repository.list(limit, offset)]

    @app.post(
        "/videos", response_model=VideoRecord, status_code=201,
        responses={202: {"model": VideoRecord, "description": "Audio extraction queued"}},
        openapi_extra={"requestBody": {"required": True, "content": {
            "multipart/form-data": {"schema": {"type": "object",
                "required": ["file"], "properties": {
                    "file": {"type": "string", "format": "binary"}}}}}}},
    )
    async def upload_video(request: Request, response: Response, background: bool = False) -> VideoRecord:
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "multipart/form-data":
            raise ServiceError("multipart_required", "Send multipart/form-data with one file field.", 415)
        async with request.form(max_files=1, max_fields=0) as form:
            uploaded = form.get("file")
            if not isinstance(uploaded, UploadFile) or not uploaded.filename or len(form) != 1:
                raise ServiceError("file_required", "Provide exactly one video in the file field.")
            if background:
                response.status_code = 202
            return await run_in_threadpool(
                enqueue_upload if background else service.upload, uploaded.file, uploaded.filename,
                uploaded.content_type or "application/octet-stream",
            )

    @app.post('/videos/{video_id}/jobs', response_model=Job, status_code=202)
    def submit_job(video_id: UUID, request: JobRequest):
        if request.action == "extract_audio":
            raise ServiceError("upload_job_only", "Use a background upload or retry its existing job.", 422)
        return jobs.submit(video_id, request)

    @app.get('/videos/{video_id}/jobs', response_model=list[Job])
    def list_jobs(video_id: UUID):
        service.get(video_id)
        return jobs.list(video_id)

    @app.get('/videos/{video_id}/jobs/{job_id}', response_model=Job)
    def get_job(video_id: UUID, job_id: UUID):
        service.get(video_id)
        return jobs.get(video_id, job_id)

    class RetryJob(BaseModel):
        key: UUID

    @app.post('/videos/{video_id}/jobs/{job_id}/retry', response_model=Job, status_code=202)
    def retry_job(video_id: UUID, job_id: UUID, request: RetryJob):
        return jobs.retry(video_id, job_id, request.key)

    @app.post('/videos/{video_id}/jobs/{job_id}/cancel', response_model=Job)
    def cancel_job(video_id: UUID, job_id: UUID):
        return jobs.cancel(video_id, job_id)

    @app.get("/videos/{video_id}", response_model=VideoRecord)
    def get_video(video_id: UUID) -> VideoRecord:
        return audio_status(service.get(video_id))

    @app.post('/videos/{video_id}/transcriptions', response_model=TranscriptRun, status_code=201,
              responses={200: {'model': TranscriptRun, 'description': 'Existing matching transcript'}})
    def transcribe_video(video_id: UUID, request: TranscriptRequest, response: Response) -> TranscriptRun:
        """Send {} for a fresh run with language detection. Set reuse_completed to accept an exact match."""
        run, reused = transcription.create_or_reuse(video_id, request)
        response.status_code = 200 if reused else 201
        return run

    @app.get('/videos/{video_id}/transcriptions', response_model=list[TranscriptRun])
    def list_transcriptions(video_id: UUID) -> list[TranscriptRun]:
        return transcription.list(video_id)

    @app.get('/videos/{video_id}/transcriptions/{run_id}', response_model=TranscriptRun)
    def get_transcription(video_id: UUID, run_id: UUID) -> TranscriptRun:
        return transcription.get(video_id, run_id)

    @app.get('/videos/{video_id}/transcript', response_model=TranscriptRun)
    def latest_transcript(video_id: UUID) -> TranscriptRun:
        """Latest successful run; use /transcriptions for failed/in-progress attempts."""
        return transcription.latest(video_id)

    @app.post('/videos/{video_id}/claim-extractions', response_model=ClaimRun, status_code=201)
    def extract_claims(video_id: UUID, request: ClaimRequest) -> ClaimRun:
        """Create an English heuristic candidate run. {} selects the latest successful transcript."""
        return claims.create(video_id, request)

    @app.get('/videos/{video_id}/claim-extractions', response_model=list[ClaimRun])
    def list_claim_extractions(video_id: UUID) -> list[ClaimRun]:
        return claims.list(video_id)

    @app.get('/videos/{video_id}/claim-extractions/{run_id}', response_model=ClaimRun)
    def get_claim_extraction(video_id: UUID, run_id: UUID) -> ClaimRun:
        return claims.get(video_id, run_id)

    @app.get('/videos/{video_id}/claims', response_model=ClaimRun)
    def latest_claims(video_id: UUID) -> ClaimRun:
        """Latest successful extraction; inspect transcript_run_id for its source version."""
        return claims.latest(video_id)

    @app.post('/videos/{video_id}/decompositions', response_model=DecompositionRun, status_code=201)
    def decompose_claims(video_id: UUID, request: DecompositionRequest) -> DecompositionRun:
        """{} selects latest successful claims. Inspect per-parent status and unresolved_count."""
        return decomposition.create(video_id, request)

    @app.get('/videos/{video_id}/decompositions', response_model=list[DecompositionRun])
    def list_decompositions(video_id: UUID) -> list[DecompositionRun]:
        return decomposition.list(video_id)

    @app.get('/videos/{video_id}/decompositions/{run_id}', response_model=DecompositionRun)
    def get_decomposition(video_id: UUID, run_id: UUID) -> DecompositionRun:
        return decomposition.get(video_id, run_id)

    @app.get('/videos/{video_id}/propositions', response_model=DecompositionRun)
    def latest_propositions(video_id: UUID) -> DecompositionRun:
        """Latest completed decomposition, including parents that need review."""
        return decomposition.latest(video_id)

    @app.post('/videos/{video_id}/retrievals', response_model=RetrievalRun, status_code=201)
    def retrieve_evidence(video_id: UUID, request: RetrievalRequest) -> RetrievalRun:
        """Select proposition IDs. Inspect per-proposition status; passages are not verdicts."""
        return retrieval.create(video_id, request)

    @app.get('/videos/{video_id}/retrievals', response_model=list[RetrievalRun])
    def list_retrievals(video_id: UUID) -> list[RetrievalRun]:
        return retrieval.list(video_id)

    @app.get('/videos/{video_id}/retrievals/{run_id}', response_model=RetrievalRun)
    def get_retrieval(video_id: UUID, run_id: UUID) -> RetrievalRun:
        return retrieval.get(video_id, run_id)

    @app.post('/videos/{video_id}/evidence-mappings', response_model=MappingRun, status_code=201)
    def map_evidence(video_id: UUID, request: MappingRequest) -> MappingRun:
        """Map 1–12 saved passages. 201 means run created; inspect status/errors."""
        return mapping.create(video_id, request)

    @app.get('/videos/{video_id}/evidence-mappings', response_model=list[MappingRun])
    def list_mappings(video_id: UUID) -> list[MappingRun]:
        return mapping.list(video_id)

    @app.get('/videos/{video_id}/evidence-mappings/{run_id}', response_model=MappingRun)
    def get_mapping(video_id: UUID, run_id: UUID) -> MappingRun:
        return mapping.get(video_id, run_id)

    @app.post('/videos/{video_id}/evidence-rankings', response_model=RankingRun, status_code=201)
    def rank_evidence(video_id: UUID, request: RankingRequest) -> RankingRun:
        """Rank a saved M6 run. Group counts are not independent confirmations."""
        return ranking.create(video_id, request)

    @app.get('/videos/{video_id}/evidence-rankings', response_model=list[RankingRun])
    def list_rankings(video_id: UUID) -> list[RankingRun]:
        return ranking.list(video_id)

    @app.get('/videos/{video_id}/evidence-rankings/{run_id}', response_model=RankingRun)
    def get_ranking(video_id: UUID, run_id: UUID) -> RankingRun:
        return ranking.get(video_id, run_id)

    @app.post('/videos/{video_id}/confidence-runs', response_model=ConfidenceRun, status_code=201)
    def create_confidence(video_id: UUID, request: ConfidenceRequest) -> ConfidenceRun:
        """Score a completed verification; this is not a truth probability."""
        return confidence.create(video_id, request)

    @app.get('/videos/{video_id}/confidence-runs', response_model=list[ConfidenceRun])
    def list_confidence(video_id: UUID) -> list[ConfidenceRun]:
        return confidence.list(video_id)

    @app.get('/videos/{video_id}/confidence-runs/{run_id}', response_model=ConfidenceRun)
    def get_confidence(video_id: UUID, run_id: UUID) -> ConfidenceRun:
        return confidence.get(video_id, run_id)

    @app.post('/videos/{video_id}/verifications', response_model=VerificationRun, status_code=201)
    def verify_evidence(video_id: UUID, request: VerificationRequest) -> VerificationRun:
        """Summarize selected evidence; inspect coverage, citations and limitations."""
        return verification.create(video_id, request)

    @app.get('/videos/{video_id}/verifications', response_model=list[VerificationRun])
    def list_verifications(video_id: UUID) -> list[VerificationRun]:
        return verification.list(video_id)

    @app.get('/videos/{video_id}/verifications/{run_id}', response_model=VerificationRun)
    def get_verification(video_id: UUID, run_id: UUID) -> VerificationRun:
        return verification.get(video_id, run_id)

    return app

app = create_app()
