# Progress

## Milestone 1
- [x] Inspect repository: empty; no existing source or repository instructions.
- [x] Commit architecture and implementation plan before application code.
- [x] Establish backend packages and environment configuration.
- [x] Implement health, multipart upload and UUID lookup APIs.
- [x] Add request/file limits and FFprobe content validation.
- [x] Add UUID local storage and atomic persistent metadata via interfaces.
- [x] Add FFmpeg interface/adapter and failure cleanup.
- [x] Add unit/API and real FFmpeg integration tests.
- [x] Add Docker/development configuration and CI workflow.
- [x] Document exact setup, semantics and limitations.
- [x] Observe successful automated tests and HTTP smoke check.
- [x] Record exact tested commit and results; no failing tests.
- [x] Verify Docker build and real video upload through running container.
- [x] Milestone 1 implementation and automated validation complete.
- [x] PR #1 merged; user verified upload and UUID lookup locally.

## Observed validation — September 14, 2026
Tested implementation commit: ad258a0c88ec8c8a077342920fdcd38867a6a32b.
[GitHub Actions run](https://github.com/jimmyhanh/VerifiStream-factchecker/actions/runs/34869109329):
- 29 tests passed, 0 failures, 0 skips; pytest completed in 1.17 seconds.
- Includes real FFmpeg generation/extraction and invalid-media integration tests.
- Uvicorn startup and HTTP health smoke check passed.
- Docker Compose image built and started successfully.
- Real generated video uploaded through the container; extraction status completed.
- Two upstream test-library deprecation warnings (Starlette/httpx and AnyIO).
  CI actions also emitted Node runtime deprecation notices; neither blocked checks.
The authoring session has no local Python/terminal; these results were executed
on GitHub Actions and verified from job logs. This subsequent change only records
results in documentation; the application/test/container source is unchanged.

[Draft PR #1](https://github.com/jimmyhanh/VerifiStream-factchecker/pull/1).
Known limits: synchronous, single-process local development; JSON metadata;
no authentication, durable jobs, crash recovery or retention management.
See README and architecture for deployment prerequisites.

## Next
M1–M2 merged and exercised locally. M3 English heuristic baseline implemented;
validation details below. M4 conservative baseline implemented; see below.

## Milestone 2
- [x] Inspect merged main (398b041) and document implementation plan.
- [x] Add transcript schemas, provider/repository interfaces and local adapters.
- [x] Add timestamped local CPU transcription with bounded subprocess execution.
- [x] Preserve historical runs and version/provenance metadata.
- [x] Add create/list/specific/latest-successful transcript APIs.
- [x] Update Docker, environment example and usage documentation.
- [x] Add API/schema/error tests; 51 tests passed before real-model test was added.
- [x] Real-model speech/silence validation: 52 tests passed locally (26.00s).
- [x] CI: 52 passed (7.17s); Docker speech transcription and HTTP checks passed.
- [x] Open draft PR #2 for review.
- [x] PR #2 merged as 36ab8ad; user screenshots confirm local transcription and retrieval.


### Milestone 2 observed validation — September 23, 2026
Implementation commit: 65cb1543b501eb9ef36b47b44098dcb2d431f5ca.
[CI run](https://github.com/jimmyhanh/VerifiStream-factchecker/actions/runs/35809661647)
passed both test and container jobs. All 52 tests ran, including real multilingual
base-model inference on the JFK fixture and an empty-speech test. No skipped or
failed tests. Two upstream test-client deprecation warnings remain.
The built container accepted a generated spoken video and returned a completed
transcription with the expected keyword. The measured container transcription
was 3.729s on this short fixture, not a general performance guarantee.

A local PyAV 18.1.0 import crash was fixed by pinning 16.1.0. The authoring
workspace's SOCKS proxy additionally required socksio locally; normal GitHub CI
and the Docker container succeeded without that workspace-only dependency.
This final documentation update changes no application or test code.
PR: https://github.com/jimmyhanh/VerifiStream-factchecker/pull/2
Next: M3 baseline (see below), followed by M4 atomic propositions.


## Milestone 3 — September 24, 2026
- [x] Inspect merged main 36ab8ad; write docs/milestone-3.md before code.
- [x] English deterministic ClaimProvider baseline with explicit limitations.
- [x] Exact source spans, enclosing segment timestamps, no invented quote text.
- [x] Provider/repository interfaces, immutable run history and snapshots/hashes.
- [x] Create/list/specific/latest-successful extraction APIs.
- [x] Input/output bounds, unsupported-language errors, process-local admission.
- [x] API/error/concurrency/real FFmpeg pipeline tests and evaluation metric test.
- [x] Synthetic development/held-out dataset and reproducible exact-span report.
- [x] Local tests: 73 passed, 1 skipped, 1 upstream test-client warning in 1.43s.
- [x] Real Uvicorn HTTP health/create/retrieve smoke trial on a synthetic saved transcript.
- [x] README, architecture, environment/Compose and CI updated.
- [x] CI: 74 tests passed with real ASR; Docker upload/transcription/claim routes passed.
- [x] PR #3 merged into main as 71de992.
- [ ] User local claim extraction trial not independently confirmed.

The local skip is the opt-in real speech-model regression test; the new extraction
provider itself is real and deterministic, not mocked. Real FFmpeg ingestion plus
injected transcription and real extraction passed locally. Docker is unavailable
in the authoring environment; the GitHub container job was executed and verified
from its logs, including real ASR and the new claim endpoints.

Held-out synthetic baseline: 9 TP, 1 FP, 5 FN; precision 90.0%, recall 64.3%,
F1 75.0%. Development: 12 TP, 1 FP, 0 FN. These single-author synthetic labels
are not independent annotations or a representative real-video benchmark.
Raw errors are retained; rules were not tuned against the held-out report.
M3 delivers an experimental detection baseline, not broad semantic accuracy.
No factual verification or Evidence Confidence is implemented. Next: M4, with
semantic-provider and independent-label quality improvements tracked separately.

### Observed M3 CI validation
Tested implementation: 576a832e5ad6534f3c4b12eb73e2fb68fadcfa99.
[CI run 35957251020](https://github.com/jimmyhanh/VerifiStream-factchecker/actions/runs/35957251020):
74 passed, 0 failed, 0 skipped, 1 upstream test-client warning; 6.95 seconds on
Python 3.11. Includes real speech/silence inference and FFmpeg integration.
Both test and container jobs succeeded. The container accepted uploaded video,
transcribed the speech fixture, created a completed claim run, and retrieved the
same persisted run through HTTP. The JFK exhortation fixture yielded zero claim
candidates, which is a valid empty result; the positive factual extraction path
is covered by the separate real-FFmpeg/injected-transcript test and HTTP trial.
Evaluation artifact was uploaded by CI. Upstream GitHub Action Node deprecation
notices remain non-blocking. This final update only records validation in docs.

Draft PR: https://github.com/jimmyhanh/VerifiStream-factchecker/pull/3


## Milestone 4 — September 30, 2026 UTC
- [x] Inspect merged main 71de992 and write docs/milestone-4.md before code.
- [x] Replaceable English decomposition provider, schemas and repository.
- [x] Supported coordination plus explicit attribution/year context preserved.
- [x] Positive policy quantity assertions split into outcome and causal propositions.
- [x] Ambiguous or unsupported grammar abstains with per-parent needs_review.
- [x] Exact source parts, parent IDs, related IDs, transcript timing and snapshot hashes.
- [x] Immutable create/list/specific/latest-completed runs, optional candidate selection.
- [x] Bounded input/output, lineage validation, busy/error handling and safe logs.
- [x] Local regression: 125 passed, 1 optional real-ASR skip, 1 upstream warning (3.17s).
- [x] Real FFmpeg + injected transcription + M3/M4 end-to-end test passed.
- [x] Real Uvicorn HTTP M3/M4 four-proposition policy trial passed (synthetic transcript).
- [x] Synthetic evaluation dataset and reproducible per-case outcome report.
- [x] README, architecture, progress, roadmap and CI updated.
- [x] Observe M4 GitHub CI: 126 tests passed; container checks succeeded.
- [ ] User review/merge and local decomposition trial.

Evaluation: 24 authored synthetic regression cases; 12 resolved, 12/15 clear cases
exactly matched, all 9 annotated ambiguous cases abstained. Proposition precision
21/21 and recall 21/27 on this small set are not general accuracy estimates.
The corpus exposed a negated-causation kind bug that was fixed, so it is explicitly
not held out. Acquired/sold, doubled/halved and written
“twenty percent” forms abstain with an explicit review reason.
No evidence has been retrieved or checked. Next: M5 evidence retrieval.

### Observed M4 CI validation
Tested implementation: 319004fbcac4ac804e83284d51272886354cad88.
[CI run 36680185527](https://github.com/jimmyhanh/VerifiStream-factchecker/actions/runs/36680185527):
126 passed, 0 failed, 0 skipped, 1 upstream test-client warning in 5.81 seconds.
Both test and container jobs succeeded. Tests include real speech inference and
FFmpeg regression. Docker uploaded and transcribed the speech fixture, extracted
claims, created a completed decomposition, and retrieved the same persisted result.
The JFK exhortation fixture produced zero candidates/propositions; the positive
four-proposition path is covered separately by integration tests and the local
HTTP trial on a synthetic saved transcript. The evaluation artifact was uploaded.
Upstream GitHub Action deprecation notices remain non-blocking. This documentation
update records the tested implementation without changing executable code.

Draft PR: https://github.com/jimmyhanh/VerifiStream-factchecker/pull/4

## Milestone 5 — October 7, 2026
- [x] Inspect merged M4 3db6107; write docs/milestone-5.md before code.
- [x] Replaceable Brave discovery, public HTTPS fetching, text/passages and JSON repository.
- [x] Typed runs with decomposition snapshot/hash, exact text offsets and version metadata.
- [x] Explicit proposition selection, missing-context outcomes and separate user context.
- [x] Manual source URL mode, duplicate URL/content linkage and visible fetch failures.
- [x] Create/list/specific retrieval APIs; immutable terminal history and process-local admission.
- [x] Local regression: 161 passed, 1 optional real-ASR skip, 1 warning in 2.39 seconds.
- [x] Six-case authored passage evaluation: 2 TP, 2 FP, 1 FN, 1 TN; exact offsets pass.
- [x] README, environment/Compose, architecture, evaluation and workflow updated.
- [x] Observe GitHub CI and separate public-source network trial (details below).
- [ ] Real credentialed Brave search trial (operator API key required).
- [ ] User review/merge and local M5 trial.

Local public-source trial attempted both Python documentation URLs and returned
`dns_failed` in the restricted authoring environment. No successful live fetching
or Brave search is claimed from that attempt. The optional CI network trial reports
its own result artifact; a green test job alone does not imply this trial passed.
M5 lexical passage selection is deliberately a candidate baseline: 50% precision
and 66.7% recall on six tiny synthetic examples are not search quality estimates.
No evidence mapping, verdict, source-independence assessment or confidence score.
M4 merge is confirmed as 3db6107; its unchecked combined merge/local-trial item
above remains historical, with the local trial still unconfirmed.

### Final M5 validation
Implementation 1d8489679f2c36b95adce0827bbf2bbce749e6ac passed
[CI run 37678381878](https://github.com/jimmyhanh/VerifiStream-factchecker/actions/runs/37678381878):
164 tests passed, zero failures/skips, one upstream warning in 7.84 seconds.
The container build and existing media/transcription/claim/decomposition checks
passed. M5 API persistence and error paths are covered by the automated suite.
Final local suite: 163 passed, one optional real-ASR skip, one warning in 2.56s.
Real Uvicorn startup and HTTP health passed locally.

The first CI live trial fetched the Python FAQ but encountered gzip on the second
source despite requesting identity encoding. Bounded gzip support and malformed/
oversized gzip tests were added. The final live trial fetched both URLs: 19,680 and
9,494 extracted characters, respectively, each with three exact-offset passages.
Both sites belong to the Python organization; this is not independent corroboration
or a credentialed search trial. The separately logged trial was inspected directly,
not inferred from the non-blocking job's green status.

Draft PR: https://github.com/jimmyhanh/VerifiStream-factchecker/pull/5
Implementation and automated validation are ready for review. Real Brave discovery
requires an operator key in the untracked .env; do not send secrets in chat.

## Milestone 6 — 2026-10-18

- [x] Inspect repository; branch from unmerged M5 without merging PR #5.
- [x] Document implementation plan and semantic boundaries.
- [x] Strict relationship/abstention schemas and replaceable provider interface.
- [x] Optional OpenAI structured-output adapter, explicit model/key configuration.
- [x] Revalidate input lineage and exact citation offsets; reject fabricated quotes.
- [x] Preserve prompts, model IDs, usage, snapshots and immutable mapping history.
- [x] POST/list/get mapping API; bounded selections, concurrency and partial failures.
- [x] Authored semantic evaluation cases and opt-in live evaluation runner.
- [x] Local regression tests: 195 passed, 1 optional real-ASR skip, 1 upstream warning.
- [x] Observe CI and container checks for the published M6 branch.
- [ ] Credentialed live model trial and human review of semantic outputs.
- [ ] M5 credentialed Brave trial, dependency-order review/merge and user local trial.

No key was supplied or external model invoked during implementation. Contract tests
use deterministic fixtures and do not establish semantic accuracy or injection
resistance. M6 adds no aggregate verdict, Evidence Confidence or source independence.

### M6 CI validation and review
Implementation `81dfc4d02661fc988ea638bfb480bf738a8060b5` passed
[CI run 39176012000](https://github.com/jimmyhanh/VerifiStream-factchecker/actions/runs/39176012000):
**196 tests passed in 9.19 seconds**, no failures or skips. Docker build, upload,
real speech transcription, claim extraction and decomposition checks passed. M6 API
and persistence are exercised by the automated suite; no live LLM was called.

[Draft PR #6](https://github.com/jimmyhanh/VerifiStream-factchecker/pull/6) is stacked
on PR #5. Both remain unmerged. The following documentation commit only records
validation; the implementation tested by CI is the SHA above.

## Milestone 7 — 2026-10-26

- [x] Inspect repo and merged PRs. M5 is in main; M6 was merged afterward into the
  M5 branch. M7 branches from that M6-containing commit and targets main.
- [x] Write design and implementation plan before coding.
- [x] Pure versioned ranking and conservative dependence grouping interfaces.
- [x] Equal priority for support/contradiction/qualification; preserve all passages.
- [x] Exact URL/content and near-copy links; transitive groups with explanations.
- [x] Optional quoted user assessments/origins, explicitly unverified provenance.
- [x] Unknown independence retained; no confidence, political score or verdict.
- [x] Immutable snapshot/history API with lineage validation and error handling.
- [x] Automated unit/API tests: local suite 212 passed, one optional real-ASR skip,
  one upstream Starlette warning in 47.00s.
- [x] Authored grouping evaluation: 4 TP, 0 FP, 1 FN, 3 TN. The missed paraphrased
  copy demonstrates a known limit. Eight synthetic cases are not held-out accuracy.
- [x] Publish draft PR and observe CI/container validation.
- [ ] User review/merge and local ranking preview.
- [ ] Credentialed Brave and M6 semantic acceptance (still unconfirmed).

No new API keys, model calls or dependencies are needed for M7. Ranking only consumes
existing M6 snapshots. Next milestone remains M8 evidence-based verification; M9
Evidence Confidence is a separate later algorithm.

### M7 CI and review
Implementation `7e3176c299a445f1a7f3088aafc0168cbe9fa3ee` passed
[CI run 40352607206](https://github.com/jimmyhanh/VerifiStream-factchecker/actions/runs/40352607206):
**213 tests passed in 6.75s**, no skips/failures. Docker build and existing real-media
pipeline checks passed. M7 API validation/persistence is covered in the automated
suite. Real local Uvicorn health returned 200 and exposed the ranking routes.
[Draft PR #7](https://github.com/jimmyhanh/VerifiStream-factchecker/pull/7) targets
main and includes M6's previously unintegrated merge. No merge performed.
A follow-up documentation-only commit records these results. Live Brave/M6 semantic
acceptance is still unconfirmed and no independence accuracy claim is made.

## Longer-upload configuration — 2026-10-26

- [x] Inspect current settings, Compose overrides and media duration checks.
- [x] Raise development defaults to 1800 seconds / 500 MiB, FFmpeg timeout 600
  seconds and transcription timeout 1800 seconds; preserve environment overrides.
- [x] Document existing .env migration and distinguish processing time from duration.
- [x] Local regression suite: 215 passed, one optional ASR skip, one upstream warning.
- [x] Generated 1800-second video: upload HTTP 201 and completed real FFmpeg audio extraction.
- [ ] Observe CI/container checks for this configuration PR.
- [ ] Operator trial with a real longer video on the user's hardware.

No new livestream implementation or performance claim. M8 remains the next milestone.

## Milestone 8 — 2026-10-28

- [x] Inspect main (includes M6/M7 and longer-upload PR #8); write implementation plan.
- [x] Implement versioned selected-evidence policy for all five evidence statuses.
- [x] Preserve disagreements without vote counts, including within dependence groups.
- [x] Explicit selected/unresolved/unmapped coverage and insufficient-evidence results.
- [x] Exact citations, original proposition/timestamps, inherited explanations/caveats.
- [x] Revalidate lineage and replay known M7 outputs; reject unknown versions.
- [x] POST/list/get API, immutable snapshot histories and sanitized failures.
- [x] Local suite: 250 passed, one optional real-ASR skip, one upstream warning in 15.12s.
- [x] Real Uvicorn health HTTP 200 and verification OpenAPI routes confirmed.
- [x] Twelve authored preclassified policy cases agree with the rules (not factual accuracy).
- [x] Publish draft PR and observe CI/container results.
- [ ] Operator local trial, review and merge.
- [ ] Credentialed M5/M6 semantic acceptance remains unconfirmed.

M8 makes no new model/search call and computes no Evidence Confidence. The status
scope is selected retrieved evidence; one-source support does not mean independent
corroboration. Unmapped retrieved passages remain explicitly outside the selected
scope. Next milestone is M9; no aggregate compound-statement verdict is introduced.

### M8 CI and review
Implementation `a15be70b5ea1434cd9912a2af80f5184766923b1` passed
[CI run 40730890484](https://github.com/jimmyhanh/VerifiStream-factchecker/actions/runs/40730890484):
**251 tests passed in 13.33s**, no skips/failures. Docker build and existing
real-media pipeline checks passed. M8 API persistence, statuses and citations are
covered by the automated suite, not a credentialed live accuracy test.
[Draft PR #9](https://github.com/jimmyhanh/VerifiStream-factchecker/pull/9) targets
main. No merge performed. The following docs-only commit records these results.

## Milestone 9 — October 28, 2026

- [x] Inspect merged M8 PR #9 and main `ded699b129b8a88ead46a54759cde869824a70e4`.
- [x] Write the scoring contract and implementation plan in `milestone-9.md` before code.
- [x] Implement separate typed confidence algorithm/repository/service interfaces.
- [x] Add versioned component scores, conservative caps, unknown signals and scope.
- [x] Group suspected copies; preserve conflict; never score political bias or truth probability.
- [x] Replay M7/M8 lineage; reject changed records and unsupported policy versions.
- [x] Add immutable snapshot/hash histories and POST/list/get confidence-run APIs.
- [x] Add 26 automated tests, including ten exact authored policy regression cases.
- [x] Run full local suite: **276 passed, 1 optional real-ASR skip**, 9.66 seconds.
- [x] Real Uvicorn HTTP health returned 200; M9 OpenAPI routes verified.
- [x] Update README, architecture, roadmap and evaluation guidance.
- [x] Observe CI and container validation on the published implementation commit.
- [ ] User exercises a score run on their own completed M8 verification.
- [ ] Held-out human evaluation/calibration (not claimed by these synthetic tests).

Local suite includes real FFmpeg integration. One upstream Starlette/httpx deprecation
warning remains. No new dependency, environment setting or external model call was
introduced. Docker is unavailable in the local authoring environment; CI is the
container validation gate. Score weights/caps are provisional; unknown quality,
independence and temporal adequacy cap v1 at 75. M8 statuses remain unchanged.
Next milestone: M10 frontend dashboard; live input remains M12.

### M9 observed CI validation

Implementation commit: `ba3f7df4969e3625286c08f8838013d870305e56`.
Implementation tree: `d8f1bc839e1b6d7be747309791ef569cb2fc29aa`.
[CI run 40775966145](https://github.com/jimmyhanh/VerifiStream-factchecker/actions/runs/40775966145):
**277 passed in 11.65 seconds**, zero failures/skips, including the real-ASR test.
Both test job 123125218581 and container job 123125218257 completed successfully.
Docker built/started, real generated video upload and speech transcription passed,
and existing claim/decomposition container smoke checks passed. M9 API behavior is
covered by the automated fixture suite; no paid-provider end-to-end semantic
accuracy or calibration is claimed. Real HTTP health returned 200 in CI.
[Draft PR #10](https://github.com/jimmyhanh/VerifiStream-factchecker/pull/10).
This validation-record update changes documentation only after the tested commit.
