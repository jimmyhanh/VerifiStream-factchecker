import json
import logging
import time
from threading import BoundedSemaphore
from uuid import UUID, uuid4
from app.claims.repository import ClaimRepository
from app.claims.service import transcript_hash
from app.database.repository import VideoRepository
from app.decomposition.repository import DecompositionRepository
from app.decomposition.service import snapshot_hash
from app.models.claim import ClaimProviderInfo, ClaimRun
from app.models.proposition import (
    AtomicProposition,
    DecompositionRun,
    ParentDecomposition,
    SourcePart,
)
from app.models.review import DraftRequest, DraftResult, DraftRun, ReviewRequest
from app.models.video import utc_now
from app.review.provider import SuggestionProvider
from app.review.repository import DraftRepository
from app.evidence.provider import MappingError
from app.shared.errors import ServiceError

logger = logging.getLogger("verifistream")


class ReviewService:
    def __init__(
        self,
        videos: VideoRepository,
        claims: ClaimRepository,
        drafts: DraftRepository,
        decompositions: DecompositionRepository,
        provider: SuggestionProvider,
    ):
        self.videos, self.claims, self.drafts, self.decompositions, self.provider = (
            videos,
            claims,
            drafts,
            decompositions,
            provider,
        )
        self.capacity = BoundedSemaphore(1)

    def _video(self, video_id: UUID) -> None:
        if self.videos.get(video_id) is None:
            raise ServiceError("video_not_found", "Video was not found.", 404)

    def _source(
        self, video_id: UUID, claim_id: UUID, candidate_ids: list[UUID]
    ) -> ClaimRun:
        self._video(video_id)
        source = self.claims.get(video_id, claim_id)
        if source is None:
            raise ServiceError(
                "claims_not_found", "Claim extraction was not found.", 404
            )
        if source.status != "completed":
            raise ServiceError("claims_not_ready", "Select completed claims.", 409)
        source = source.model_copy(deep=True)
        candidates = {c.id: c for c in source.candidates}
        if not set(candidate_ids) <= candidates.keys():
            raise ServiceError(
                "candidate_not_found",
                "Candidate does not belong to this claim run.",
                404,
            )
        text = source.transcript_snapshot.text
        if (
            source.video_id != video_id
            or source.id != claim_id
            or len(candidates) != len(source.candidates)
            or transcript_hash(source.transcript_snapshot) != source.transcript_sha256
            or any(
                text[candidates[i].char_start : candidates[i].char_end]
                != candidates[i].quote
                for i in candidate_ids
            )
        ):
            raise ServiceError(
                "invalid_claim_lineage", "Original claim snapshot is inconsistent.", 409
            )
        if any(len(candidates[i].quote) > 4000 for i in candidate_ids):
            raise ServiceError(
                "review_input_too_large",
                "Each reviewed candidate must be at most 4000 characters.",
                413,
            )
        return source

    def suggest(self, video_id: UUID, request: DraftRequest) -> DraftRun:
        if not self.capacity.acquire(blocking=False):
            raise ServiceError(
                "suggestions_busy", "Another suggestion request is running.", 503
            )
        try:
            source = self._source(video_id, request.claim_run_id, request.candidate_ids)
            run = DraftRun(
                id=uuid4(),
                video_id=video_id,
                request=request.model_copy(deep=True),
                claim_snapshot=source,
                claim_snapshot_sha256=snapshot_hash(source),
                provider=self.provider.name,
                requested_model=self.provider.model,
                prompt_version=self.provider.prompt_version,
                prompt_snapshot=self.provider.prompt,
                warnings=[
                    "Unverified AI suggestions: review against the original before approval.",
                    "Drafts cannot be retrieved or verified. No factual knowledge was requested.",
                    "Conditions, attribution, negation, timing and quantities must remain intact.",
                ],
            )
            self.drafts.save(run)
            started = time.monotonic()
            for candidate in source.candidates:
                if candidate.id not in request.candidate_ids:
                    continue
                result = DraftResult(
                    candidate_id=candidate.id,
                    source_quote=candidate.quote,
                    status="failed",
                )
                try:
                    if time.monotonic() - started >= 180:
                        raise MappingError("decomposition_budget_exceeded")
                    reply = self.provider.suggest(candidate.quote)
                    result.propositions = reply.decision.propositions
                    result.review_reason = reply.decision.review_reason
                    result.returned_model, result.response_id, result.usage = (
                        reply.model,
                        reply.response_id,
                        reply.usage,
                    )
                    result.status = (
                        "proposed" if result.propositions else "needs_review"
                    )
                except MappingError as exc:
                    result.error_code = exc.code
                except Exception:
                    result.error_code = "decomposition_suggestion_failed"
                run.results.append(result)
            failed = sum(r.status == "failed" for r in run.results)
            run.status = (
                "failed"
                if failed == len(run.results)
                else "partial" if failed else "completed"
            )
            run.finished_at = utc_now()
            self.drafts.save(run)
            logger.info(
                json.dumps(
                    {
                        "event": "proposition_suggestions_finished",
                        "run_id": str(run.id),
                        "status": run.status,
                    }
                )
            )
            return run
        finally:
            self.capacity.release()

    def approve(self, video_id: UUID, request: ReviewRequest) -> DecompositionRun:
        ids = list(dict.fromkeys(item.candidate_id for item in request.items))
        source = self._source(video_id, request.claim_run_id, ids)
        parameters: dict[str, str | int | float | bool] = {
            "origin": "user_reviewed_interpretation",
            "semantic_faithfulness_verified": False,
            "approval_request_json": request.model_dump_json(),
        }
        if request.draft_run_id:
            draft = self.get(video_id, request.draft_run_id)
            if (
                draft.status == "processing"
                or draft.video_id != video_id
                or draft.id != request.draft_run_id
                or draft.request.claim_run_id != source.id
                or draft.claim_snapshot != source
                or draft.claim_snapshot_sha256 != snapshot_hash(source)
                or not set(ids) <= set(draft.request.candidate_ids)
            ):
                raise ServiceError(
                    "invalid_draft_lineage",
                    "Draft does not match the original claims.",
                    409,
                )
            parameters["draft_snapshot_json"] = draft.model_dump_json()
        results = []
        for candidate in source.candidates:
            if candidate.id not in ids:
                continue
            propositions = []
            for item in request.items:
                if item.candidate_id != candidate.id:
                    continue
                propositions.append(
                    AtomicProposition(
                        id=uuid4(),
                        parent_candidate_id=candidate.id,
                        text=item.text.strip(),
                        kind=item.kind,
                        transformation="reviewed_interpretation",
                        source_parts=[
                            SourcePart(
                                role="predicate",
                                char_start=candidate.char_start,
                                char_end=candidate.char_end,
                                quote=candidate.quote,
                            )
                        ],
                        source_quote=candidate.quote,
                        segment_ids=candidate.segment_ids,
                        start_seconds=candidate.start_seconds,
                        end_seconds=candidate.end_seconds,
                        needs_context=item.needs_context,
                    )
                )
            results.append(
                ParentDecomposition(
                    parent_candidate_id=candidate.id,
                    source_quote=candidate.quote,
                    status="decomposed" if len(propositions) > 1 else "unchanged",
                    propositions=propositions,
                )
            )
        run = DecompositionRun(
            id=uuid4(),
            video_id=video_id,
            claim_run_id=source.id,
            transcript_run_id=source.transcript_run_id,
            status="completed",
            finished_at=utc_now(),
            provider=ClaimProviderInfo(
                name="user-reviewed-propositions",
                version="reviewed-propositions-v1",
                parameters=parameters,
            ),
            pipeline_version="reviewed-atomic-v1",
            claim_snapshot_sha256=snapshot_hash(source),
            claim_snapshot=source,
            selected_candidate_ids=ids,
            results=results,
            proposition_count=len(request.items),
            warnings=[
                "User-reviewed interpretations, not verified facts. Review is not proof of semantic faithfulness.",
                "Each original candidate is retained verbatim with original timestamps; the transcript is unchanged.",
                "source_parts retain the entire original candidate; they do not prove the edited proposition.",
                "Approval records are local attestations, not authenticated reviewer identities.",
            ],
        )
        self.decompositions.save(run)
        logger.info(
            json.dumps(
                {
                    "event": "propositions_approved",
                    "run_id": str(run.id),
                    "count": len(request.items),
                }
            )
        )
        return run

    def list(self, video_id: UUID) -> list[DraftRun]:
        self._video(video_id)
        return self.drafts.list(video_id)

    def get(self, video_id: UUID, run_id: UUID) -> DraftRun:
        self._video(video_id)
        run = self.drafts.get(video_id, run_id)
        if run is None:
            raise ServiceError("draft_not_found", "Suggestion run was not found.", 404)
        return run
