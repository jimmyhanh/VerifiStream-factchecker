# Confidence policy regression cases

`cases.json` contains ten authored cases with preclassified relationships, exact
expected raw scores, capped scores, and agreement components. Run:

```sh
python -m pytest backend/tests/test_confidence.py -q
```

The tests construct complete synthetic retrieval/mapping/ranking/verification runs
using the existing fixture adapters, then exercise the actual M9 API. Sources in
these cases have lexical scores 0.9, 0.8, ... by fixture index. Separate tests cover
duplicate grouping, source-metadata non-influence, failed retrieval, and immutable
replay. The whole suite runs in CI; results are included in its JUnit artifact.

These cases test implementation against authored policy expectations. They are not
held out, contain no independent human confidence judgments, and do not measure
factual accuracy, semantic relevance, or calibration. They must never be presented
as evidence that a score of 75 means 75% correctness.

For future calibration, collect held-out proposition/evidence snapshots with human
ratings of evidence adequacy, relevance, directness, time alignment and dependence.
Split by underlying claim and original report to avoid copied-source leakage.
Record algorithm version, strata (causal, outdated, conflicting, etc.), coverage,
latency and provider cost. Compare score bands to human adequacy ratings and measure
agreement/error; probability calibration requires a separately defined binary target.
Do not tune and report on the same cases. Preserve old runs when revising weights.
