# Milestone 6 — evidence relationship mapping

## Implementation plan (2026-10-18)
Build on the M5 branch while PR #5 awaits merge. Keep M6 separate and target that
branch for review; do not merge either PR automatically.

1. Add strict request/output models and a replaceable MappingProvider interface.
2. Map explicitly selected saved passages (1–12 per run) to their original atomic
   propositions. Use an optional OpenAI structured-output adapter; no heuristic
   fallback or model-knowledge verdicts. No key means a recorded configuration error.
3. Validate snapshot hashes, IDs, exact quotations and offsets before accepting
   results. Citation URLs and offsets come from stored evidence, never model output.
4. Preserve full retrieval input, prompt, requested/returned model, response ID,
   usage, parameters, timestamps and validated decisions in immutable run history.
5. Expose POST/list/get evidence-mappings endpoints. Test provider protocol, all
   relationship labels, abstention, citation tampering, failures and API persistence.

## Semantics
SUPPORTS / CONTRADICTS / QUALIFIES / CONTEXT / IRRELEVANT describe a passage's
relationship to a proposition, not a final fact-check verdict. Uncertain scope,
entity, date, quantity, attribution or causal interpretation must abstain with
`needs_review` and a null relationship. Context is useful background, not a synonym
for uncertainty. User-supplied search context remains unverified. A reported outcome
does not establish causation. An attributed assertion does not establish its truth.

The model sees only the selected proposition, its source quote/context, and the
retrieved passage plus unverified page metadata. It has no tools or browsing.
Retrieved text is untrusted data; instructions inside it must be ignored. Exact
quotation validation prevents invented citations but cannot prove semantic accuracy
or eliminate prompt injection. Mapping labels remain model interpretations to inspect.

## Scope and limits
No verdicts, confidence, ranking, independence inference or frontend. Synchronous,
single-process JSON development storage; one mapping run at a time. Up to 12 provider
calls, bounded response bytes and socket timeouts; DNS/header waits are not a hard
worker deadline. No automatic retries or hidden paid fallback. Live provider testing
requires an operator key. Fixture tests do not measure model accuracy.

## Local validation
195 tests passed, one optional real-ASR skip and one upstream Starlette warning.
Real Uvicorn `/health` returned HTTP 200 and OpenAPI includes mapping routes.
Live credentialed semantic evaluation is pending; no accuracy claim is made.

CI run 39176012000 passed 196 tests in 9.19s on implementation 81dfc4d;
Docker build and existing media/transcription pipeline checks also passed.
Draft review: https://github.com/jimmyhanh/VerifiStream-factchecker/pull/6
