"""Attributed publisher ratings, never inferred credibility or political bias."""

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def domain(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in ("https", "http")
        or parsed.username
        or parsed.password
        or not parsed.hostname
    ):
        raise ValueError("Expected public publisher URL without credentials")
    host = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


class Rating(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(min_length=1, max_length=120)
    original_label: str = Field(min_length=1, max_length=120)
    category: Literal["Very High", "High", "Mixed", "Low", "Very Low"] | None = None
    rating_url: str = Field(max_length=2048)
    methodology_url: str = Field(max_length=2048)
    assessed_on: date | None = None
    retrieved_at: datetime
    reuse_basis: str = Field(min_length=1, max_length=1000)

    @field_validator("rating_url", "methodology_url")
    @classmethod
    def safe_link(cls, value):
        domain(value)
        if not value.startswith("https://"):
            raise ValueError("Use HTTPS attribution links")
        return value

    @model_validator(mode="after")
    def dates(self):
        if self.retrieved_at.tzinfo is None or self.retrieved_at > datetime.now(
            timezone.utc
        ):
            raise ValueError("Retrieval time must be timezone-aware and not future")
        if self.assessed_on and self.assessed_on > self.retrieved_at.date():
            raise ValueError("Assessment must not follow retrieval")
        if any(
            not s.strip()
            for s in (self.provider, self.original_label, self.reuse_basis)
        ):
            raise ValueError("Blank rating fields")
        return self


class Publisher(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    domains: list[str] = Field(min_length=1, max_length=30)
    domain_evidence_url: str
    ratings: list[Rating] = Field(max_length=10)

    @field_validator("domain_evidence_url")
    @classmethod
    def evidence(cls, value):
        domain(value)
        if not value.startswith("https://"):
            raise ValueError("Use HTTPS evidence URL")
        return value

    @field_validator("domains")
    @classmethod
    def hosts(cls, values):
        for value in values:
            if (
                domain("https://" + value) != value
                or "/" in value
                or ":" in value
                or "." not in value
            ):
                raise ValueError(
                    "Use exact normalized hostnames, without www or wildcards"
                )
        if len(set(values)) != len(values):
            raise ValueError("Duplicate domain")
        return values

    @model_validator(mode="after")
    def providers(self):
        if len({r.provider.casefold().strip() for r in self.ratings}) != len(
            self.ratings
        ):
            raise ValueError("Duplicate provider for publisher")
        return self


class RegistryData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str = Field(min_length=1, max_length=100)
    publishers: list[Publisher] = Field(max_length=10000)

    @model_validator(mode="after")
    def unique_domains(self):
        hosts = [h for p in self.publishers for h in p.domains]
        if len(hosts) != len(set(hosts)):
            raise ValueError("Ambiguous domain ownership")
        return self


class PublisherRegistry:
    def __init__(self, path: Path | None = None):
        self.data = (
            RegistryData.model_validate_json(path.read_text())
            if path
            else RegistryData(version="empty-v1", publishers=[])
        )
        self.sha256 = hashlib.sha256(self.data.model_dump_json().encode()).hexdigest()

    def lookup(self, url: str, at: datetime | None = None) -> dict:
        host = domain(url)
        at = at or datetime.now(timezone.utc)
        publisher = next((p for p in self.data.publishers if host in p.domains), None)
        ratings = []
        if publisher:
            for rating in publisher.ratings:
                record = rating.model_dump(mode="json")
                record["freshness"] = (
                    "Assessment date unknown"
                    if not rating.assessed_on
                    else (
                        "Older assessment"
                        if (at.date() - rating.assessed_on).days > 365
                        else "Assessed within 365 days"
                    )
                )
                ratings.append(record)
        return {
            "domain": host,
            "publisher": publisher.name if publisher else None,
            "status": "rated" if ratings else "unrated",
            "ratings": ratings,
            "domain_evidence_url": publisher.domain_evidence_url if publisher else None,
            "registry_version": self.data.version,
            "registry_sha256": self.sha256,
            "captured_at": at.isoformat(),
            "scope": "publication_overall",
            "notice": "External assessments, not article verdicts. Providers are shown separately; no average or political bias score.",
        }

    def snapshot(self, root: Path, run) -> None:
        at = datetime.now(timezone.utc)
        urls = sorted({c.url for result in run.results for c in result.citations})
        data = {
            "verification_id": str(run.id),
            "verification_sha256": hashlib.sha256(
                run.model_dump_json().encode()
            ).hexdigest(),
            "captured_at": at.isoformat(),
            "sources": {url: self.lookup(url, at) for url in urls},
        }
        folder = root / str(run.video_id) / "publisher-rating-snapshots"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{run.id}.json"
        if target.exists():
            raise ValueError("Rating snapshot already exists")
        temporary = folder / f"{uuid4()}.tmp"
        try:
            temporary.write_text(json.dumps(data), encoding="utf8")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate a supplied publisher registry; does not verify reuse rights or ratings."
    )
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    registry = PublisherRegistry(args.file)
    print(
        f"Valid registry {registry.data.version}: {len(registry.data.publishers)} publisher(s); sha256={registry.sha256}"
    )
