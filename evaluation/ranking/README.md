# Source dependence evaluation

Run `python evaluation/ranking/evaluate.py` after installing the backend. No API
keys/network are used. Eight authored source-pair fixtures cover identical content,
near copies, same URL, user-declared origin, unrelated topics, a shared footer,
short overlapping text and an unattributed paraphrase of a common source.

These fixtures are synthetic, not held out or independently adjudicated. The target
is detection of stipulated dependence, NOT proof of independence. Inspect the
reported false negatives: substantial paraphrases without a shared origin declaration
are intentionally outside this baseline's capabilities. A missed link leaves source
independence unknown, never independent. Report fixture counts rather than broad
accuracy claims. Real evaluation needs syndicated articles, common wire reports,
shared datasets, boilerplate-heavy pages and human-reviewed origin chains.
