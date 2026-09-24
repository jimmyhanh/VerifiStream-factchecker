# Milestone 3 implementation plan

Baseline: merged main 36ab8ad (Milestones 1–2). Scope: English check-worthy
candidate extraction only; no decomposition, web retrieval, factual verdict,
Evidence Confidence, frontend, or new model downloads.

1. Add strict claim/run schemas with exact half-open character offsets into a
   canonical transcript (`' '.join(segment.text ...)`), overlapping segment IDs,
   and enclosing ASR segment times. Times are not word alignment.
2. Add a replaceable ClaimProvider with a deterministic English rule baseline.
   Select assertions with numerical, causal or factual-event signals; exclude
   obvious questions, subjective opinions, wishes and instructions. Preserve
   compound wording, negation and repeated occurrences. Rules are deliberately
   imperfect; no generated paraphrases or truth claims.
3. Add a service validating every returned span against the frozen transcript.
   Capture provider/rules version, parameters, input hash, source transcript run,
   snapshot, elapsed time, processing/completed/failed status and safe errors.
4. Persist each extraction attempt separately through a repository protocol;
   terminal runs are immutable. Resolve latest-successful transcript once or
   accept an explicit transcript_run_id. Unsupported language returns 422.
5. Add create/list/specific/latest-successful extraction endpoints, bounded input
   and result sizes, process-local single-run admission, dependency injection.
6. Add regression/API tests including fabricated spans, cross-segment claims,
   immutable history, failed retries, unknown IDs, silence and language limits.
7. Add separate synthetic development/held-out fixtures with sentence-span gold
   labels, an exact-match precision/recall evaluator and raw error reporting.
   Report baseline measurements honestly, with no production accuracy claim.
8. Run tests/evaluation and an HTTP smoke trial; extend CI/container smoke checks;
   update README, architecture, progress and accelerated November roadmap.

Acceptance: reproducible extraction on saved transcripts without extra setup,
strict source lineage, transparent experimental rules, passing regression gates,
and measured labeled baseline. Semantic model adapters remain replaceable future
improvements; do not claim broad semantic claim-detection quality from heuristics.

## Implemented and observed
Local regression: 73 passed, 1 optional ASR test skipped, 1 upstream warning.
Real FFmpeg + fixture transcription + real claim detector pipeline passed. Real
Uvicorn HTTP create/get trial passed with a synthetic stored transcript. GitHub CI run
35957251020 subsequently passed 74 tests with no skips (6.95s) and passed the
Docker upload/transcription/extraction smoke check on implementation 576a832.
Synthetic held-out exact-span precision 90.0%, recall 64.3%, F1 75.0%; all errors
retained in evaluation/claims/baseline-v1.json. Semantic recall is a known gap,
not hidden by the completion status of a processing run.
