# Milestone 8 — evidence-based verification

## Plan (2026-10-28)
Inspect M7 and build a deterministic, provider-independent status policy, strict
schemas, immutable repository and POST/list/get API; add rule and lineage tests,
an authored evaluation set, then run regressions and CI. No new model calls.

## Scope and rules: selected-evidence-v1
Statuses summarize the selected M6 passages in an explicit M7 run, not universal
truth. The model interpretation remains upstream in M6. No internal knowledge,
political score, majority vote, lexical score, rank or user quality assessment
is allowed to decide a status. Source metadata and independence remain unverified.

Evaluate each proposition selected by the underlying M5 request, including ones
with no mapped evidence. Rules in order:
1. CONTRADICTS plus SUPPORTS or QUALIFIES => Conflicting Evidence. Never outvote
   contrary evidence, even when both sides share a dependence group.
2. Any selected failed/needs_review mapping => Insufficient Evidence (unless rule 1
   already exposes a known conflict). Keep resolved citations and explain the gap.
3. CONTRADICTS only among decisive relationships => Contradicted.
4. QUALIFIES (with or without SUPPORTS) => Partially Supported.
5. SUPPORTS => Supported.
6. Only context/irrelevant/no mappings => Insufficient Evidence.

QUALIFIES inherits M6's definition of partial support/material qualification. This
policy does not independently establish semantic correctness. Unmapped M5 passages
are counted and warned about, but are outside the explicitly selected M6 evidence
set; no complete-search claim is made. A proposition with no selected mapping is
Insufficient Evidence. No aggregate verdict across a compound parent claim.

## Provenance and safety checks
Revalidate the complete mapping/retrieval lineage, exact quotations and annotations;
replay the known M7 algorithm version/parameters to check groups and rankings were
not silently altered. Reject unknown ranking versions instead of guessing. Persist
full ranking snapshot/hash, policy version, parameters, timestamps, rule IDs and
per-proposition decisions. Source URL, quote, offsets, metadata and group membership
come from stored records, never from newly generated prose. Include M6 explanations
and caveats as attributed model interpretations. Group totals are descriptive;
never label them independent confirmations. Repetition cannot increase a vote.

## Limits and acceptance
No new web/model calls or dependencies. Pure policy with a replaceable interface;
JSON single-process development storage, synchronous requests, immutable terminal
runs. No Evidence Confidence (M9) or dashboard (M10). A one-source Supported result
is explicitly limited to the selected evidence and does not imply independent
corroboration. M5/M6 live quality validation is still unconfirmed. Fixture tests
measure rule behavior, not factual accuracy of the full pipeline.

## Local validation
250 tests passed, one optional real-ASR skip and one upstream warning in 15.12s.
Real Uvicorn health and verification OpenAPI checks passed. All twelve authored,
preclassified policy cases matched expectations; this is not end-to-end accuracy.
