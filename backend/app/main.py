from uuid import UUID
from fastapi import FastAPI, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from app.api.limits import UploadLimits
from app.database.repository import JsonVideoRepository, VideoRepository
from app.media.ffmpeg import FFmpegProcessor, MediaProcessor
from app.models.video import HealthResponse, VideoRecord, PublicConfiguration
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
) -> FastAPI:
    config = settings or Settings.from_env()
    video_storage = storage or LocalVideoStorage(config.storage_root)
    video_repository = repository or JsonVideoRepository(config.storage_root)
    transcripts = transcript_repository or JsonTranscriptRepository(config.storage_root)
    claim_records = claim_repository or JsonClaimRepository(config.storage_root)
    decomposition_records = decomposition_repository or JsonDecompositionRepository(config.storage_root)
    retrieval_records = retrieval_repository or JsonRetrievalRepository(config.storage_root)
    mapping_records = mapping_repository or JsonMappingRepository(config.storage_root)
    ranking_records = ranking_repository or JsonRankingRepository(config.storage_root)
    verification_records = verification_repository or JsonVerificationRepository(config.storage_root)
    confidence = ConfidenceService(video_repository, verification_records,
        confidence_repository or JsonConfidenceRepository(config.storage_root),
        confidence_algorithm or TransparentConfidenceAlgorithm())
    verification = VerificationService(video_repository, ranking_records,
        verification_records,
        verification_policy or SelectedEvidencePolicy())
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
    app = FastAPI(title="VerifiStream", version="0.1.0")
    app.add_middleware(
        UploadLimits, max_bytes=config.max_video_bytes + 64 * 1024,
        slots=config.max_concurrent_uploads,
    )

    app.add_middleware(CORSMiddleware, allow_origins=config.cors_origins,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
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

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """Liveness only; does not guarantee storage/media-tool readiness."""
        return HealthResponse()

    @app.get("/configuration", response_model=PublicConfiguration)
    def public_configuration() -> PublicConfiguration:
        return PublicConfiguration(max_video_bytes=config.max_video_bytes,
                                   max_duration_seconds=config.max_duration_seconds)

    @app.get("/videos", response_model=list[VideoRecord])
    def list_videos(limit: int = Query(default=50, ge=1, le=100),
                    offset: int = Query(default=0, ge=0)) -> list[VideoRecord]:
        return video_repository.list(limit, offset)

    @app.post(
        "/videos", response_model=VideoRecord, status_code=201,
        openapi_extra={"requestBody": {"required": True, "content": {
            "multipart/form-data": {"schema": {"type": "object",
                "required": ["file"], "properties": {
                    "file": {"type": "string", "format": "binary"}}}}}}},
    )
    async def upload_video(request: Request) -> VideoRecord:
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "multipart/form-data":
            raise ServiceError("multipart_required", "Send multipart/form-data with one file field.", 415)
        async with request.form(max_files=1, max_fields=0) as form:
            uploaded = form.get("file")
            if not isinstance(uploaded, UploadFile) or not uploaded.filename or len(form) != 1:
                raise ServiceError("file_required", "Provide exactly one video in the file field.")
            return await run_in_threadpool(
                service.upload, uploaded.file, uploaded.filename,
                uploaded.content_type or "application/octet-stream",
            )

    @app.get("/videos/{video_id}", response_model=VideoRecord)
    def get_video(video_id: UUID) -> VideoRecord:
        return service.get(video_id)

    @app.post('/videos/{video_id}/transcriptions', response_model=TranscriptRun, status_code=201)
    def transcribe_video(video_id: UUID, request: TranscriptRequest) -> TranscriptRun:
        """Create a new run; waits for completion. Send {} to auto-detect language."""
        return transcription.create(video_id, request)

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
