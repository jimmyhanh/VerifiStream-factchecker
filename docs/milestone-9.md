# Milestone 9 — Evidence Confidence

## Implementation plan

Add a separate deterministic ConfidenceAlgorithm interface, typed results, immutable
JSON run repository, and synchronous POST/list/get APIs at
`/videos/{video_id}/confidence-runs`. Input is an explicit completed M8 verification
UUID. Preserve its complete snapshot and hash. Replay known M7/M8 versions before
scoring; reject changed lineage or unknown versions. Do not modify M8 statuses.
No model call, API key, dependency, frontend, or live processing is added.

## Version 1 scoring contract

`evidence-confidence-v1` is an **uncalibrated evidence adequacy heuristic**, not a
probability of truth or measured accuracy. Scope is selected retrieved evidence.
The score applies equally to supporting and contradictory evidence. Conflict
lowers adequacy for a settled assessment, even though documenting conflict is useful.

Five components, each worth at most 20 points:

- Mapping resolution: mapped / selected passages (including context/irrelevant).
- Retrieved coverage: mapped / retrieved passages. This is not web-wide coverage.
- Lexical relevance: mean of the maximum lexical relevance of decisive passages
  in each dependence group. Lexical overlap is not semantic correctness.
- Useful amount: min(decisive dependence groups / 3, 1). Suspected copies share
  one group; different groups do not establish independence.
- Agreement: 1 when decisive labels have no supporting/qualifying versus
  contradictory conflict; 0 on any such conflict. No majority voting.

Sum contributions, round to nearest integer (half up), then apply the lowest cap:
75 for unknown quality/independence/temporal adequacy; 50 for only one decisive
group; 50 for conflict; 25 for any unresolved selected mapping or failed/incomplete
retrieval; 0 for no decisive evidence. All applicable caps are returned.
Unknown source quality, directness, primary/secondary role, independence and
claim-relative recency are returned as null, with reasons. Unverified metadata and
caller assessments receive no score bonus. A recent publication alone cannot
establish relevance to a historical or causal claim.

These provisional weights/caps are design choices, not learned or validated against
human judgments. Changing them requires a new version; existing runs remain intact.
Exact quotations establish provenance only. M6 semantic errors can propagate.
Repeating the same passage cannot increase useful amount or group-maximum relevance;
a newly selected passage with higher lexical overlap can raise that group maximum; added unresolved/unselected passages can still change coverage penalties.
Paraphrased copies may evade M7 grouping. High scores cannot resolve that limitation.

## Acceptance checks

Test exact component arithmetic, supported/contradicted symmetry, duplicate
invariance, conflicts not outvoted, zero-evidence behavior, unresolved and incomplete
retrieval caps, ignored user metadata, bounds, deterministic replay, immutable
history/restart, request validation, tampering rejection, and sanitized failures.
Run the entire backend suite and a real HTTP health/OpenAPI smoke test. Add an
explicit synthetic policy regression dataset; it is not factual accuracy or calibration.

## Preview

After building this branch, open http://localhost:8000/docs. Complete M8 first.
POST `/videos/{video_id}/confidence-runs` with:

```json
{"verification_run_id": "ACTUAL_COMPLETED_M8_RUN_UUID"}
```

Use the actual upload video UUID in the path. The body UUID identifies a verification
run, not the video or ranking. GET the collection to inspect history, or append the
returned confidence run `id` to fetch one run. HTTP 201 means a run was created;
check `status` and inspect each result's `evidence_confidence`, `components`, `caps`,
`unknown_signals`, citations in `verification_snapshot`, and warnings.
No additional environment variables are required.

## Remaining work

Held-out human adjudicated evaluation and calibration are deferred. This milestone
does not claim a calibrated confidence score. Next: M10 dashboard, then M11 jobs and
caching, and M12 live input. Local JSON is still a single-process development adapter.


## Observed validation — October 28, 2026

Implementation `ba3f7df4969e3625286c08f8838013d870305e56`: local full suite
276 passed, 1 optional ASR skip; CI 277 passed in 11.65 seconds with no skips.
[CI run](https://github.com/jimmyhanh/VerifiStream-factchecker/actions/runs/40775966145)
also passed Docker build and existing real-media/transcription/claim/decomposition
container checks. All ten authored confidence cases matched exact expected scores.
Real Uvicorn HTTP health and M9 OpenAPI routes were verified locally. These results
establish regression behavior, not confidence calibration or real-world accuracy.
