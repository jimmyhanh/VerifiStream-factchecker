# Atomic decomposition evaluation

From repository root after the editable backend dev install:

```
python evaluation/decomposition/evaluate.py
```

`dataset.json` has 24 synthetic, project-authored examples, not independently
annotated or held out. They test intended behavior and expose missing grammar,
not real-world accuracy. Unlike M3, all input candidates are supplied directly;
these measurements exclude transcription errors and M3 missed claims.

Gold annotations specify exact normalized text and proposition kind. They concern
faithful decomposition, not whether the underlying assertions are true. Attribution
must remain in normalized text; quoted content is not endorsed. Unsupported or
ambiguous structures can abstain (`needs_review`), producing no atomic assertions.
Cases needing review are distinct from clear cases that the current grammar misses.

Observed `english-atomic-v1` results:
- 12/24 inputs resolved: 50.0% coverage.
- 12/15 clear, annotated resolvable inputs exactly matched: 80.0%.
- All 9 annotated ambiguous inputs abstained; 0 unsafe resolutions in this corpus.
- 21/21 emitted propositions matched exact text/kind: precision 100% on this tiny set.
- 21/27 expected propositions found: recall 77.8%; abstentions count as misses.

Do not report 100% general accuracy from the precision figure. Three clear cases
(acquired/sold, doubled/halved and written-number “twenty percent”) abstain.
Unsupported policy-effect patterns return needs_review rather than silently
returning an incomplete outcome/causation split.
These three misses remain in `baseline-v1.json`. Tests/evaluation also caught a
negated-causation kind bug, which was corrected; this corpus is explicitly a
regression/development corpus, not a held-out test after that correction.

Metrics: resolution coverage uses all inputs; exact success uses all gold
resolvable inputs, including model abstentions. Proposition precision is exact
(text,kind) set intersection / emitted set size; recall uses all expected
propositions across resolvable inputs. Any assertion emitted for an annotated
ambiguous input counts as an extra prediction and an unsafe resolution. Empty
metric denominators return null. Per-case missing/extra propositions are retained.
These set metrics do not evaluate occurrence multiplicity; separate unit/API tests
cover IDs, source spans, order, repeated source occurrences and history.

Next evaluation: independently review real-video labels; expand time/quantity,
negation and attribution coverage; keep parent claims together when creating
fresh development/held-out splits; measure pipeline recall as well as isolated M4.
