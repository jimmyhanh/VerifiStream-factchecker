# Verification policy fixtures

Run `python evaluation/verification/evaluate.py` after installing the backend.
Twelve authored cases exercise all five statuses, duplicate reports, qualifications,
missing evidence and unresolved mappings. They are **preclassified** M6 inputs.
The outdated and causal examples assume M6 has already classified scope correctly;
M8 cannot repair a wrong upstream relationship by inspecting labels alone.

This measures conditional rule agreement, not fact-check accuracy, search coverage,
independence, model quality or confidence calibration. The set is not held out.
Integration tests additionally validate exact citations, group membership, immutable
histories, incomplete selection reporting and rejection of altered snapshots.

Next evaluation work: independently label real claim/passage pairs, adjudicate
scope/causation disagreements, reserve held-out cases, then measure full-pipeline
status accuracy alongside abstention coverage and citation correctness. No new
paid API calls or live verification accuracy claims are made by this fixture set.
