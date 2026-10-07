# Retrieval evaluation

`python evaluation/retrieval/evaluate.py` reproduces `baseline-v1.json`.
Six single-author synthetic query/source pairs test whether lexical selection
returns candidate text and whether offsets match exactly. They are development
fixtures, not held out, not independent labels and not a live-search benchmark.
Expected usefulness here means direct claim-relevant content; topical context may
still be returned for later M6 classification. The v1 result is 2 TP, 2 FP, 1 FN,
1 TN: precision 50%, recall 66.7%, exact substring checks all pass. The synonym case
and two topical-only examples expose known limitations. No tuning to conceal them.

`python evaluation/retrieval/live_smoke.py` is an optional real public-source fetch
trial using two Python-owned pages. It records no source text, only hashes/counts.
It uses no paid search API, and cannot establish source independence or verification
quality. Network or site failures must be reported, not silently replaced by mocks.
Credentialed Brave discovery still requires an operator-provided API key.
