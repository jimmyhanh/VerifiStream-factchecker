# Milestone 7 — transparent ranking and source dependence

## Plan — 2026-10-26
Inspect M6 mapping snapshots, add pure versioned algorithms, then API/repository
adapters, tests and documentation. M6 was merged into the M5 branch after M5 reached
main. This branch includes that M6 merge and targets main to restore the intended
integration path. Do not merge automatically.

## Decisions
- Accept an explicit completed or partial M6 mapping run; retain its full snapshot
  and hash. Revalidate lineage, passage IDs, status and exact quotations.
- Rank within each proposition, never across unrelated claims. SUPPORTS,
  CONTRADICTS and QUALIFIES share the highest tier; CONTEXT follows. Abstentions,
  failed mappings and irrelevant passages remain inspectable, outside the useful
  evidence list. No final verdict or confidence score.
- Within each tier, order by declared directness, declared primary/secondary role,
  then existing lexical relevance, and stable passage UUID. Both metadata signals
  default to unknown. Optional human assessments require exact source quotation
  offsets and a rationale; they remain user-supplied/unverified, not AI facts.
- Promote different dependence groups within the same tier before repeated members.
  Keep all passages and all contradiction labels; never silently drop duplicates.
- Group sources by identical final URL, identical nonempty text, or suspected near
  duplicates (5-token shingle Jaccard >=0.90, at least 100 tokens each and 50 unique
  shingles). Store pairwise reasons/scores. Near-duplicate grouping is a heuristic;
  boilerplate and syndication are not reliably distinguished.
- Allow explicit, separately stored user-declared common origins with exact
  attribution quotes. Shared declarations link sources conservatively but are not
  verified origin extraction. Do not infer origin from publisher/domain alone.
- Components are transitive dependence groups, not proof that every pair is a copy.
  Singleton independence remains unknown; group count is NOT independent-source count.
- Dates, publisher and source type are displayed unchanged and unverified. No
  publisher reputation or recency bonus: newer is not inherently better for a
  historical claim. No political scores, network calls or new dependencies.

## Acceptance
Unit tests cover duplicate/syndicated text, unrelated text sharing boilerplate,
short passages, transitive groups, stable ordering, equal treatment of opposing
relationships and metadata provenance. API tests cover immutable histories,
restart, partial runs, tampering and invalid/foreign IDs. An authored deterministic
fixture set measures grouping behavior only, not broad real-world independence.
Live M5/M6 credentialed quality acceptance remains separate and pending.

## Local results
212 automated tests passed, one optional real-ASR skip and one upstream warning.
Eight authored dependence fixtures: 4 TP, 0 FP, 1 FN, 3 TN; the unlinked paraphrase
is a known limitation, not independent evidence. No paid provider call was made.
