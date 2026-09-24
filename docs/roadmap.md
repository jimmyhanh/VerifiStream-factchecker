# Revised roadmap through November 13, 2026

Revised at the user's request to target a demonstrable uploaded-video MVP before
mid-November. November 13 is the working delivery target; November 14 is a buffer,
not a confirmed course deadline. The original December route is retained in git
history. Work milestone by milestone; acceptance gates determine readiness.

| Dates | Milestones | Acceptance gate/status |
|---|---|---|
| Completed | M1: upload/audio; M2: transcription | Merged, tested, exercised locally |
| Sep 23–25 | Baseline and fixtures | Clean setup, saved demo clips, progress reconciliation |
| Sep 26–Oct 2 | M3: check-worthy candidates | English heuristic implemented early; versioned source spans, measured precision/recall; semantic quality remains limited |
| Oct 3–7 | M4: atomic propositions | Preserve qualifiers, split compound/causal assertions, link to source |
| Oct 8–15 | M5: evidence retrieval | Source metadata, exact passages/snapshots, failure handling |
| Oct 16–20 | M6: relationship mapping | Five relationship labels tied to proposition/passage IDs |
| Oct 21–24 | M7: ranking/independence | Directness/relevance and common-origin grouping |
| Oct 25–29 | M8: verification | Five statuses from retrieved evidence, append-only runs |
| Oct 30–Nov 2 | M9: Evidence Confidence | Separate deterministic versioned experimental scorer |
| Nov 3–7 | M10: dashboard | Upload-to-evidence inspection, uncertainty, citations/history |
| Nov 8–10 | Integration/evaluation | End-to-end regression and labeled results |
| Nov 11–13 | Freeze and delivery | Fresh setup rehearsal, report, presentation, recorded fallback |
| Nov 14 | Contingency | Release blockers only |
| After reliable MVP | M11: jobs/caching/scaling | Measured bottlenecks, PostgreSQL/durable tasks/object storage |
| Deferred | M12: near-real-time | Chunk boundaries, revisions, latency/backpressure |

## Scope and risk management
- Planning assumption: one developer with roughly 15–20 focused hours/week.
- Short English demo videos, around 1–3 minutes; inspect/select 3–5 candidates.
  This is a demo scope, not a change to the current upload limit.
- Preserve transparency, source lineage and failure handling when reducing scope.
- By October 15 retrieval must work; by October 29 backend verification must work;
  by November 7 the dashboard must complete the workflow.
- Move minimal durable-job/database work earlier if HTTP latency becomes unreliable.
- Label cached evidence and experimental scores honestly. Do not claim calibration
  from a small dataset or use the number of websites as source independence.
- No live processing, Kubernetes, Kafka, or premature microservices for this demo.
- Continue collecting evaluation fixtures at each milestone; M3's synthetic labels
  need independently reviewed real transcript examples before broad quality claims.
