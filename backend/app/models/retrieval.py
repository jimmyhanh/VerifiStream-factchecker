from datetime import datetime
from typing import Literal, Self
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.proposition import DecompositionRun
from app.models.video import utc_now


class RetrievalRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decomposition_run_id: UUID | None = None
    proposition_ids: list[UUID] = Field(min_length=1, max_length=3)
    # User context is separate from source assertions; never silently edit M4.
    contexts: dict[UUID, str] = Field(default_factory=dict)
    mode: Literal['search', 'manual_urls'] = 'search'
    source_urls: dict[UUID, list[str]] = Field(default_factory=dict)

    @model_validator(mode='after')
    def selection(self) -> Self:
        ids = set(self.proposition_ids)
        if len(ids) != len(self.proposition_ids):
            raise ValueError('Proposition IDs must be unique')
        if not set(self.contexts) <= ids or not set(self.source_urls) <= ids:
            raise ValueError('Context and URLs must reference selected propositions')
        if any(not v.strip() or len(v) > 300 for v in self.contexts.values()):
            raise ValueError('Context must contain 1 to 300 characters')
        if self.mode == 'manual_urls':
            if set(self.source_urls) != ids:
                raise ValueError('Manual mode needs URLs for every selected proposition')
            if any(not 1 <= len(urls) <= 5 or any(len(u) > 2048 for u in urls)
                   for urls in self.source_urls.values()):
                raise ValueError('Provide 1 to 5 URLs of at most 2048 characters')
        elif self.source_urls:
            raise ValueError('Search mode does not accept manual URLs')
        return self


class SearchHit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    url: str = Field(max_length=2048)
    title: str | None = Field(default=None, max_length=1000)
    snippet: str | None = Field(default=None, max_length=3000)


class EvidencePassage(BaseModel):
    id: UUID
    source_id: UUID
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    text: str
    lexical_relevance: float = Field(ge=0, le=1)


class SourceSnapshot(BaseModel):
    id: UUID
    requested_url: str
    final_url: str
    domain: str
    title: str | None = None
    publisher: str | None = None
    publication_date: str | None = None
    metadata_origin: str = 'page_declared_unverified'
    source_type: str = 'unknown'
    primary_secondary: str = 'unknown'
    independence: str = 'unknown'
    fetched_at: datetime = Field(default_factory=utc_now)
    content_type: str
    text: str
    text_sha256: str
    raw_sha256: str
    extractor_version: str = 'html-text-v1'
    duplicate_of_source_id: UUID | None = None


class FetchAttempt(BaseModel):
    url: str
    status: Literal['fetched', 'duplicate_url', 'failed']
    source_id: UUID | None = None
    error_code: str | None = None


class PropositionRetrieval(BaseModel):
    proposition_id: UUID
    query: str
    user_context: str | None = None
    context_origin: str | None = None
    status: Literal['retrieved', 'no_passages', 'needs_context', 'failed', 'partial']
    hits: list[SearchHit] = Field(default_factory=list)
    attempts: list[FetchAttempt] = Field(default_factory=list)
    passages: list[EvidencePassage] = Field(default_factory=list)
    error_code: str | None = None


class RetrievalRun(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: UUID
    video_id: UUID
    decomposition_run_id: UUID
    decomposition_snapshot: DecompositionRun
    decomposition_sha256: str
    request: RetrievalRequest
    status: Literal['processing', 'completed', 'failed'] = 'processing'
    created_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    elapsed_seconds: float | None = None
    discovery_provider: str
    pipeline_version: str = 'retrieval-v1'
    passage_algorithm_version: str = 'lexical-windows-v1'
    parameters: dict[str, str | int | float]
    results: list[PropositionRetrieval] = Field(default_factory=list)
    sources: list[SourceSnapshot] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None = None
