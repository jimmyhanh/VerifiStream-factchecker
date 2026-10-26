from datetime import datetime
from typing import Literal, Self
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.mapping import MappingRun, Relationship
from app.models.video import utc_now


class QuotedAnnotation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    quote: str = Field(min_length=1, max_length=2000)
    rationale: str = Field(min_length=1, max_length=800)

    @model_validator(mode='after')
    def nonempty(self) -> Self:
        if not self.quote.strip() or not self.rationale.strip() or self.char_end <= self.char_start:
            raise ValueError('Provide a nonempty exact quotation and rationale')
        return self


class EvidenceAssessment(QuotedAnnotation):
    directness: Literal['direct', 'indirect', 'unknown'] = 'unknown'
    source_role: Literal['primary', 'secondary', 'unknown'] = 'unknown'


class OriginDeclaration(QuotedAnnotation):
    origin_url: str = Field(min_length=1, max_length=2048)


class RankingRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mapping_run_id: UUID
    # Keys identify passages for assessments and sources for origin declarations.
    assessments: dict[UUID, EvidenceAssessment] = Field(default_factory=dict, max_length=12)
    origins: dict[UUID, OriginDeclaration] = Field(default_factory=dict, max_length=15)


class DependenceLink(BaseModel):
    left_source_id: UUID
    right_source_id: UUID
    reason: Literal['same_final_url', 'identical_text', 'near_duplicate_text', 'shared_declared_origin']
    similarity: float | None = None
    origin_url: str | None = None
    provenance: Literal['deterministic', 'heuristic', 'user_supplied_unverified']


class SourceGroup(BaseModel):
    id: UUID
    source_ids: list[UUID]
    independence: Literal['unknown', 'dependence_detected_or_suspected']
    links: list[DependenceLink]


class RankedPassage(BaseModel):
    passage_id: UUID
    source_id: UUID
    group_id: UUID
    relationship: Relationship
    rank: int
    tier: Literal['claim_evidence', 'context']
    directness: Literal['direct', 'indirect', 'unknown']
    source_role: Literal['primary', 'secondary', 'unknown']
    assessment_origin: Literal['unknown', 'user_supplied_unverified']
    lexical_relevance: float
    group_repeat: bool
    citation_url: str
    publisher: str | None
    publication_date: str | None
    source_type: str
    reasons: list[str]


class UnrankedPassage(BaseModel):
    passage_id: UUID
    source_id: UUID
    reason: Literal['needs_review', 'failed', 'irrelevant']


class PropositionRanking(BaseModel):
    proposition_id: UUID
    ranked: list[RankedPassage] = Field(default_factory=list)
    unranked: list[UnrankedPassage] = Field(default_factory=list)
    useful_source_count: int = 0
    useful_dependence_group_count: int = 0
    independence: Literal['unknown'] = 'unknown'


class RankingRun(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: UUID
    video_id: UUID
    request: RankingRequest
    mapping_snapshot: MappingRun
    mapping_sha256: str
    status: Literal['processing', 'completed', 'failed'] = 'processing'
    created_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    elapsed_seconds: float | None = None
    ranking_version: str = 'transparent-order-v1'
    grouping_version: str = 'source-dependence-v1'
    parameters: dict[str, str | int | float | bool]
    groups: list[SourceGroup] = Field(default_factory=list)
    results: list[PropositionRanking] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None = None
