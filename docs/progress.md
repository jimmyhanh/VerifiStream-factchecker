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
validation details below. M4 not started.

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
- [ ] User review/merge and local claim extraction trial.

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
