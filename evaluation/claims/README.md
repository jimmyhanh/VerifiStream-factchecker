# Check-worthy claim baseline

Run from repository root after `pip install -e './backend[dev]'`:

```
python evaluation/claims/evaluate.py --output evaluation/claims/baseline-v1.json
```

No search, model download or API key is needed. This evaluates candidate selection,
not factual truth, source evidence, atomic decomposition or Evidence Confidence.

`dataset.json` contains 24 synthetic examples (48 sentences), 12 examples per
split. Labels were authored for this project, not independently human annotated.
The provider was implemented before inspecting held-out results; do not tune
rules-v1 on those errors and still call that split held out. Any later iteration
needs a fresh held-out set with independently reviewed labels and real transcript
examples. These figures are not production accuracy estimates.

Gold positives: externally checkable past/present factual assertions, including
attributed statements, causal and compound claims. Negatives: questions, opinions,
preferences, wishes, commands, forecasts and conditionals. This is an MVP labeling
policy, not a universal definition of check-worthiness. A quoted assertion is an
assertion attributed to a speaker, not an endorsement or verified fact.

Each gold sentence's character span is computed in the documented canonical text.
All examples from a case stay in one split. Matching is exact half-open [start,end)
character spans; one match counts once. An overbroad span is both an extra
prediction and a missed gold span. Metrics: TP/(TP+FP) precision, TP/(TP+FN)
recall, 2TP/(2TP+FP+FN) F1; undefined zero-denominator values are null. No token
accuracy or true-negative-heavy accuracy metric is substituted for recall.

Observed rules-v1 baseline:

| Split | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Development | 12 | 1 | 0 | 92.3% | 100% | 96.0% |
| Held out | 9 | 1 | 5 | 90.0% | 64.3% | 75.0% |

See `baseline-v1.json` for every error. Verb vocabulary misses treated/collapsed/
received and grammatical variants. Non-numerical assertions may be missed. Lucky
number statements can be selected. Whole-sentence opinion filters may suppress
embedded factual content. Missing ASR punctuation may merge statements. Repeated
occurrences are preserved, not deduplicated. These are known baseline limitations.
A semantic adapter and broader annotation are quality improvements, not hidden
capabilities of the current detector.
