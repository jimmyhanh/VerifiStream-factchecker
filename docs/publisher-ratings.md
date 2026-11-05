# Attributed publisher reliability ratings

## Architecture and scope

Use a replaceable local JSON registry of externally supplied publication-level ratings.
No model-generated reputation, political bias or numeric trust score. Exact normalized
domains (only leading www is normalized) match publisher records; no suffix inheritance,
no wildcard matches, no automatic trust for .gov/.edu. Maintainers document domain
ownership evidence. Validation checks structure, not actual ownership or truth.

Each provider retains its original label, optional maintainer category, source and
methodology URLs, assessment date if known, retrieval timestamp and documented reuse
basis. Providers are not averaged. Unknown assessment dates and assessments older than
365 days are visibly flagged; the 365-day cutoff is a display convention, not a measure
of accuracy. An unrated publisher is not low reliability. No score is fed into verification
or Evidence Confidence. A highly rated publication can still publish irrelevant or wrong
articles. These ratings do not prove passage relevance or source independence.

GET /publisher-ratings?url=... returns current registry data without fetching that URL.
The registry is loaded at startup. Invalid configured files fail startup rather than
silently supplying misleading ratings. Missing configuration gives an empty registry.
New completed verification runs capture separate immutable rating snapshots, preserving
existing nested model serialization and hashes. GET /videos/{id}/verifications/{run}/
publisher-ratings returns the snapshot after validating its verification hash. Existing
runs without snapshots show historical information unavailable; current ratings are
never substituted. Snapshot persistence errors are logged without changing the evidence
verdict; the UI explicitly reports unavailable historical ratings. Deleting a video also
removes its snapshots.

## Supplying real ratings

The default config/publisher-ratings.json is intentionally empty. No Ground News,
Ad Fontes, or MBFC data has been imported and no rights to their datasets are implied.
Supply data you have permission to use and display, with attribution and a reuse_basis
explaining that permission (no API keys, contracts or secrets). This field records your
basis; validation does not determine legal permission. Confirm domain associations and
provider labels against the supplied source, and increment registry version on updates.

Schema example (fictional; not a real publisher assessment):

```json
{
  "version": "authorized-import-v1",
  "publishers": [{
    "name": "Fictional test publisher",
    "domains": ["example.org"],
    "domain_evidence_url": "https://example.org/about",
    "ratings": [{
      "provider": "Fictional evaluator",
      "original_label": "High",
      "category": "High",
      "rating_url": "https://ratings.example/review",
      "methodology_url": "https://ratings.example/method",
      "assessed_on": "2020-01-01",
      "retrieved_at": "2020-02-01T00:00:00Z",
      "reuse_basis": "Synthetic example only; replace with your authorized data"
    }]
  }]
}
```

Validate using an installed backend environment:
`python -m app.publishers.registry config/publisher-ratings.json`
Docker Compose mounts config read-only and sets PUBLISHER_RATINGS_FILE automatically.
After editing the registry, run `docker compose restart backend` (initial code update:
`docker compose up --build -d`). Native development can set PUBLISHER_RATINGS_FILE to
an absolute JSON path. Reload Evidence to see current ratings; new Findings capture the
new registry while existing Findings retain their original snapshots. No paid provider
requests or subscriptions are automatically initiated by this feature.

## Validation

Backend tests cover exact matching/spoofed suffixes, untrusted URL schemes, missing
ratings, provider disagreement, invalid registries, original-label preservation, stale
dates, snapshot stability, legacy absence and unchanged confidence compatibility.
Browser test uses a clearly fictional evaluator and example.org to test attribution,
methodology links, saved snapshot labels and reload. Production registry stays empty.
