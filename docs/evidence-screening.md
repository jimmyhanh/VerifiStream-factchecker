# Evidence screening and clearer findings

## Plan and implementation

Improve atomic proposition selection and context controls with larger checkboxes,
strong outlines, selected-state text and keyboard focus outlines. Add default-on,
explicitly disclosed screening after the user initiates retrieval. Reuse existing
mapping APIs and their 12-passage bound; no provider call occurs on loading a page.
Round-robin across proposition queues sorted by lexical relevance. Remaining passages
remain Not screened. This is bounded triage, not exhaustive verification; manual mapping
can assess other selections. Each mapping run retains its own exact selection and lineage.

Display relationships and explanations on passage cards before the user chooses what
to inspect. SUPPORTS, CONTRADICTS and QUALIFIES have equal priority, then CONTEXT,
unknown/unresolved, and IRRELEVANT. No relationship is hidden and no source is promoted
based on agreement alone. Selection for a different manual mapping run is still allowed.

A single Build findings & confidence action chains ranking, verification and confidence
using actual returned IDs. Stop on failures; retain completed stages. Exact history
ancestry validation remains active; no latest-run substitutions or backend schema changes.
Existing stage controls remain for inspection and retry. Confidence bands are a version-1
presentation convention (0–24 very limited,25–49 low,50–74 moderate,75–100 high), not
calibrated truth probabilities. Existing score values, caps, policy and hashes stay intact.

Findings explain unresolved mappings, outside-selection passages, failed fetches and no
decisive evidence separately from the evidence status. The current conservative policy
still reports Insufficient Evidence when unresolved mapping blocks a conclusion. We do
not increase confidence or suppress disagreements just to produce a stronger result.

## Validation

Ten frontend unit tests cover source/context helpers plus screening balance/cap,
relationship ordering, confidence-band boundaries and gap explanations. Browser test
adds automatic screening -> findings/confidence -> reload with exact ancestry. Existing
manual workflow tests explicitly turn off automatic screening. CI validates both flows,
backend regression and Docker. No live paid provider calls in tests.

## Observed acceptance results

CI run 41913452397 passed on commit 9e1892bede0199297190003929d285bb379fdcff:
302 backend tests, 10 frontend unit tests, 15 Playwright checks, production build,
TypeScript checking and Docker smoke checks. Automatic screening through confidence
and reload ancestry passed. An older selection-limit test was narrowed to proposition
cards so it does not count the new automatic-screening toggle.
