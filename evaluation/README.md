# Evaluation (future milestones)

No evaluation pipeline is implemented in Milestone 1.
Build a versioned labeled dataset covering supported, contradicted, partial,
compound, outdated, causal, conflicting, insufficient, duplicated-source and
misleading claims. Preserve retrieved snapshots and citation passage offsets.
Split development and held-out cases; prevent source/claim leakage.
Track extraction precision/recall, atomic decomposition, retrieval success,
relevance, citation correctness, verdict accuracy, confidence calibration,
latency and provider cost. Evidence Confidence is not probability of truth.

## Available now
The M3 candidate selection baseline is in [claims/README.md](claims/README.md).
Its synthetic precision/recall figures do not evaluate factual verification.

M4 decomposition coverage and faithfulness fixtures are in
[decomposition/README.md](decomposition/README.md); these are synthetic regression
examples, not independently annotated real-video performance.

M5 passage fixtures and an optional public-fetch trial are under `retrieval/`.
Reported lexical results are not evidence-relationship, verdict or live-search
accuracy. See that directory's README for denominators and raw errors.
