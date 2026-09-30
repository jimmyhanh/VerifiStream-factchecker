# Milestone 4 plan

Base: merged M3, main 71de992. Implement atomic proposition decomposition only.
No evidence retrieval, verdicts, Evidence Confidence, LLM calls or frontend.

- Add replaceable DecompositionProvider and repository protocols, source-linked
  Pydantic records and create/list/specific/latest-successful APIs.
- Consume one explicit or latest-successful claim extraction snapshot. Optional
  candidate IDs select a subset; never reconstruct claims from model memory.
- Initial English grammar handles recognized simple clauses and coordinated
  predicates/full clauses, plus explicit attribution and leading year context.
- Separate positive policy-caused numerical changes/job creation into observed
  outcome and causal assertion. Link related propositions. Do not infer occurrence
  from negated, hypothetical or modal causation.
- Preserve exact source fragments. Render propositions by copying fragments and
  a small versioned set of explicit transformations. Record transformations;
  generated normalized wording is not presented as a verbatim quote.
- Return a per-parent needs_review outcome with no atomic assertions for ambiguous
  or unsupported grammar. Completed processing does not mean all parents resolved.
- Preserve terminal runs, source snapshot/hash, provider version/parameters and
  time lineage. Validate input lineage, provider spans, lexical coverage, output
  bounds, safe errors and process-local concurrency.
- Test compounds, qualifiers, numbers/units, negation, attribution, repeated
  occurrences, context and unsafe causal inferences, plus API persistence/failure.
- Evaluate synthetic labeled supported/ambiguous examples with coverage and exact
  proposition-set matching; report abstentions and errors, not general accuracy.
- Update README/progress/architecture and CI; run tests, HTTP and Docker CI checks.

Semantic understanding remains limited by the grammar and M3 candidate recall.
Unknown entities/dates are never filled in. A future semantic provider still needs
faithfulness evaluation; source-span validity alone does not prove entailment.

## Completion and validation
Implemented as draft [PR #4](https://github.com/jimmyhanh/VerifiStream-factchecker/pull/4).
The latest endpoint returns the latest completed run; inspect per-parent outcomes
and unresolved_count because completed processing may contain needs_review results.

- Local regression: 125 passed, 1 optional real-ASR skip, 1 warning in 3.17s.
- CI implementation 319004fbcac4ac804e83284d51272886354cad88:
  [126 passed, no skips, 1 warning in 5.81s](https://github.com/jimmyhanh/VerifiStream-factchecker/actions/runs/36680185527).
- Docker upload/transcription/claim/decomposition persistence checks passed.
  Its speech fixture yields zero candidates; positive policy decomposition is
  exercised by separate integration tests and a real HTTP synthetic-transcript trial.
- Authored synthetic regression corpus: 12/15 clear cases matched exactly;
  all 9 ambiguous cases abstained. Overall resolved coverage: 12/24.
  Three clear cases remain unsupported. This is not independent accuracy evidence.

README contains setup and endpoint instructions. Review/merge and a user trial
on real project videos remain outstanding. Next milestone: evidence retrieval.
