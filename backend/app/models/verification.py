from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.mapping import Relationship
from app.models.ranking import RankingRun
from app.models.video import utc_now

EvidenceStatus = Literal['Supported', 'Partially Supported', 'Contradicted',
                         'Conflicting Evidence', 'Insufficient Evidence']


class VerificationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ranking_run_id: UUID


class VerificationCitation(BaseModel):
    passage_id: UUID
    source_id: UUID
    group_id: UUID
    relationship: Relationship
    url: str
    quote: str
    char_start: int
    char_end: int
    title: str | None
    publisher: str | None
    publication_date: str | None
    source_type: str
    primary_secondary: str
    metadata_origin: str
    mapping_explanation: str
    mapping_caveats: list[str]


class EvidenceCoverage(BaseModel):
    retrieved_passages: int
    selected_passages: int
    mapped_passages: int
    unresolved_passage_ids: list[UUID]
    unmapped_passage_ids: list[UUID]
    retrieval_status: str
    failed_fetch_count: int


class PropositionVerification(BaseModel):
    proposition_id: UUID
    parent_candidate_id: UUID
    proposition_text: str
    source_quote: str
    start_seconds: float
    end_seconds: float
    evidence_status: EvidenceStatus
    rule_id: str
    explanation: str
    scope: Literal['selected_retrieved_evidence'] = 'selected_retrieved_evidence'
    coverage: EvidenceCoverage
    citations: list[VerificationCitation]
    # One group can have opposing labels; keep them, do not majority-vote.
    group_relationships: dict[UUID, list[Relationship]]
    decisive_source_count: int
    decisive_dependence_group_count: int
    independence: Literal['unknown'] = 'unknown'
    limitations: list[str]


class VerificationRun(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: UUID
    video_id: UUID
    request: VerificationRequest
    ranking_snapshot: RankingRun
    ranking_sha256: str
    policy_version: str
    parameters: dict[str, str | int | float | bool]
    status: Literal['processing', 'completed', 'failed'] = 'processing'
    created_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    elapsed_seconds: float | None = None
    results: list[PropositionVerification] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None = None
