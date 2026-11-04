# Context suggestions and source assessment

## Implementation plan and decisions

Add local, deterministic suggestions beside each selected atomic proposition's search
context. Preserve the manual field, immutable claim, per-proposition association, and
existing 300-character limit. Copy dates/relative times verbatim; never infer the year
from today's date. Show the complete original quotation for extracted values. Offer at
most the immediately preceding/following transcript segments within 30 seconds, taken
from the selected run's exact transcript ancestry. Users decide whether those quotations
are relevant. Long quotations are omitted rather than truncated. Search-direction
prompts for numeric, historical and causal claims are explicitly not factual assertions.
Clicking appends without overwriting manual edits or exceeding limits; duplicate clicks
are disabled. Existing retrieval snapshots retain the submitted context; suggestion
origins are displayed but are not stored as separately audited approval records.
No external model calls, new dependencies, secrets, or backend model changes are needed.

## Source trust request

Display a source assessment on retrieved passages and final citations. The current
retriever captures page-declared, unverified metadata; it does not evaluate correction
history, editorial/research methodology or verified independent confirmation. Therefore
v1 returns a null numeric score and **Not rated**, with the available publisher/date/
source-type/primary-secondary metadata and explicit unknowns. Unknown is not zero trust.
This is a transparent profile, not yet the requested calibrated numeric trust score.
It never uses political bias or publisher-name reputation guesses. It does not change
Evidence Confidence or verification results. A future score requires provenance-backed
quality signals, a versioned rubric and evaluation before rating actual sources.

## Usage

Select a proposition on Claims. Under its Search context field click a suggested
quotation or search direction; edit the resulting text before retrieving evidence.
The existing manual field is always available. No additional `.env` values are required.
In Evidence or Findings expand **Source trust assessment: Not rated** to inspect what
is known and what is unassessed.

## Validation

Six local unit tests cover date non-invention, adjacent quotations, no truncation,
per-proposition isolation, append/deduplication/length handling, and abstention from
trust scoring even when page metadata is complete. A browser regression checks context
submission and the source assessment disclosure; browser execution remains a separate
CI acceptance check. Local TypeScript checking and production build passed. Run `npm run test:unit`, `npm run typecheck`, `npm run build` in
frontend; `npm test` also runs browser checks with synthetic providers.
