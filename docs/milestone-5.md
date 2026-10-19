# Milestone 5 implementation plan

Base: merged M4 3db6107. Scope: retrieval candidates and exact source passages,
not evidence relationships, factual verdicts or Evidence Confidence.

- Add typed retrieval runs linked to an immutable decomposition snapshot/hash.
- Select up to three propositions; explicitly flag missing context and allow
  separately recorded user-supplied search context without changing source claims.
- Replaceable SearchProvider with Brave Web Search adapter (key in environment).
  Also allow explicitly supplied source URLs for reproducible no-key development;
  label this manual discovery, not automated search.
- Fetch only public HTTPS HTML/plain text with validated redirects, pinned public
  connection addresses, TLS hostname verification, byte limits and time limits.
  Never send the search token to source websites. No browser/PDF/paywall bypass.
- Extract bounded visible text and page-declared metadata. Unknown publisher,
  date, source type, primary/secondary status and independence remain unknown.
- Persist canonical text snapshots and hashes; select exact character-offset
  passages with versioned lexical overlap scores, not semantic evidence confidence.
- Record all search hits, fetch failures, query/context and duplicate URL/content
  relationships. Different domains are not counted as independent confirmation.
- Synchronous, process-local admission and append-only terminal JSON histories;
  completed means processing finished, not adequate evidence found.
- Tests cover source lineage, context, selection, exact passages, duplicates,
  unsafe URLs/redirects, failures, credential handling and persistence. Live provider
  validation is separate and must not be claimed without an actual credentialed call.
- Update README, environment/Compose, architecture/progress and CI. Publish a PR.

Provider choice: Brave's documented Web Search endpoint returns source discovery
results with a simple token-based API. No SDK dependency is needed. The operator
must obtain a key and a plan permitting the intended storage of search results;
provider access and source-content permissions are separate. No subscription is
purchased by this milestone. References checked October 7, 2026:
https://brave.com/search/api/
https://api-dashboard.search.brave.com/app/documentation/web-search/responses

## Implementation and observed validation

Draft PR #5 implements the planned adapters, typed records and retrieval APIs.
The public fetcher also accepts gzip with compressed and decompressed byte caps,
after a real source ignored the requested identity encoding. Unsupported source
classification and independence remain unknown rather than guessed.

Tested revision: 1d8489679f2c36b95adce0827bbf2bbce749e6ac.
CI run 37678381878: 164 passed, no skips, one warning in 7.84 seconds. Container
checks succeeded. Local: 163 passed, one optional real-ASR skip, one warning.
The separate live fetch trial successfully retrieved both Python-owned sources
and selected three exact-offset passages from each. This is a fetching trial,
not evidence of independence, factual verification or automatic search quality.
The six-case lexical regression retains two false positives and one false negative.

Remaining acceptance: credentialed Brave trial, user review/merge and a real
project-video retrieval trial. No search subscription or credential was created.
