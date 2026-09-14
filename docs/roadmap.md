# September–December 2026 roadmap

Dates are planning targets; acceptance gates determine readiness. Implement one milestone at a time.
The reliable uploaded-video demonstration has priority over live processing.

| Dates | Milestones | Acceptance gate |
|---|---|---|
| Sep 14–27 | M1: upload and audio extraction | Validation, status persistence, failure cleanup, real FFmpeg tests and setup docs |
| Sep 28–Oct 11 | M2: timestamped transcription | Replaceable provider, timestamp alignment, failures and cost captured |
| Oct 12–18 | M3: check-worthy claims | Versioned extraction output and precision/recall baseline |
| Oct 19–25 | M4: atomic propositions | Compound and causal claims split with transcript linkage |
| Oct 26–Nov 1 | M5: multi-source retrieval | Source metadata, retrieved snapshots and citation provenance |
| Nov 2–8 | M6: relationship mapping | Passages map to precise proposition IDs; irrelevant evidence excluded |
| Nov 9–15 | M7: ranking and independence | Repeated reports clustered, directness/relevance evaluated |
| Nov 16–19 | M8: evidence-based verification | Five evidence statuses; insufficient evidence fallback; append-only runs |
| Nov 20–22 | M9: Evidence Confidence | Deterministic versioned scoring, contributions exposed and tested |
| Nov 23–Dec 6 | M10: dashboard | Upload-to-evidence inspection demo with citations and uncertainty |
| Dec 7–13 | Stabilization and documentation | Evaluation report, reproducible demo, recorded fallback, final report |
| After core demo is reliable | M11: jobs/caching/scaling | PostgreSQL, durable tasks, idempotent retries and measured bottlenecks |
| Stretch / next term | M12: near-real-time | Chunk boundaries, revisions, latency budget and backpressure |

## Semester risk management
- Keep demo videos short and preserve provider-independent fixtures.
- Build evaluation fixtures with each relevant milestone.
- If latency makes HTTP processing unreliable, advance the minimal durable-job
  portion of M11 before the dashboard; defer optional caching/scaling.
- No Kubernetes, Kafka, or separate microservices for this semester.
- Final demonstration target: Dec 13; adjust when the course submission date is known.
