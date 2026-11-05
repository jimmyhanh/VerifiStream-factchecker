import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from app.publishers.registry import PublisherRegistry, RegistryData, domain
from app.main import create_app
from app.shared.config import Settings
from test_verification import verification
from test_ranking import ranking
from test_mapping import mapping
from test_retrieval import setup


def data():
    return {
        "version": "fixture-v1",
        "publishers": [
            {
                "name": "Fictional test publisher",
                "domains": ["example.org"],
                "domain_evidence_url": "https://example.org/about",
                "ratings": [
                    {
                        "provider": "Fictional evaluator",
                        "original_label": "High",
                        "category": "High",
                        "rating_url": "https://ratings.example/review",
                        "methodology_url": "https://ratings.example/method",
                        "assessed_on": "2020-01-01",
                        "retrieved_at": "2020-02-01T00:00:00Z",
                        "reuse_basis": "Synthetic test data only",
                    }
                ],
            }
        ],
    }


def test_exact_matching_original_labels_and_dates(tmp_path):
    path = tmp_path / "ratings.json"
    path.write_text(json.dumps(data()))
    registry = PublisherRegistry(path)
    result = registry.lookup("https://www.example.org/story")
    assert result["status"] == "rated"
    assert result["ratings"][0]["original_label"] == "High"
    assert result["ratings"][0]["freshness"] == "Older assessment"
    for url in [
        "https://example.org.evil.com",
        "https://other.example.org",
        "https://unrated.example",
    ]:
        assert registry.lookup(url)["status"] == "unrated"
    for url in ["javascript:alert(1)", "https://user:pass@example.org"]:
        with pytest.raises(ValueError):
            registry.lookup(url)


def test_multiple_providers_not_averaged_and_invalid_registry_rejected(tmp_path):
    content = data()
    other = dict(
        content["publishers"][0]["ratings"][0],
        provider="Another evaluator",
        original_label="Mixed",
        category="Mixed",
    )
    content["publishers"][0]["ratings"].append(other)
    path = tmp_path / "ratings.json"
    path.write_text(json.dumps(content))
    result = PublisherRegistry(path).lookup("https://example.org")
    assert [r["original_label"] for r in result["ratings"]] == ["High", "Mixed"]
    assert "score" not in result
    content["publishers"].append(content["publishers"][0])
    with pytest.raises(ValidationError):
        RegistryData.model_validate(content)
    content = data()
    content["publishers"][0]["ratings"][0]["reuse_basis"] = ""
    with pytest.raises(ValidationError):
        RegistryData.model_validate(content)


def test_snapshot_remains_unchanged_after_registry_update(verification, tmp_path):
    config, client, base, ranked = verification
    run = client.post(
        base + "/verifications", json={"ranking_run_id": ranked["id"]}
    ).json()
    snapshot = client.get(base + f'/verifications/{run["id"]}/publisher-ratings')
    assert snapshot.status_code == 200, snapshot.text
    before = snapshot.json()
    path = tmp_path / "ratings.json"
    path.write_text(json.dumps(data()))
    restarted = TestClient(
        create_app(config.model_copy(update={"publisher_ratings_file": path}))
    )
    assert (
        restarted.get(
            "/publisher-ratings", params={"url": "https://example.org/report"}
        ).json()["status"]
        == "rated"
    )
    assert (
        restarted.get(base + f'/verifications/{run["id"]}/publisher-ratings').json()
        == before
    )
    assert restarted.get(base + f'/verifications/{run["id"]}').json() == run
    assert (
        restarted.post(
            base + "/confidence-runs", json={"verification_run_id": run["id"]}
        ).json()["status"]
        == "completed"
    )


def test_unavailable_snapshot_is_not_current_rating(verification):
    config, client, base, ranked = verification
    run = client.post(
        base + "/verifications", json={"ranking_run_id": ranked["id"]}
    ).json()
    path = (
        config.storage_root
        / run["video_id"]
        / "publisher-rating-snapshots"
        / f'{run["id"]}.json'
    )
    path.unlink()
    assert (
        client.get(base + f'/verifications/{run["id"]}/publisher-ratings').status_code
        == 404
    )
    assert (
        client.get(
            "/publisher-ratings", params={"url": "https://unknown.example"}
        ).json()["status"]
        == "unrated"
    )
