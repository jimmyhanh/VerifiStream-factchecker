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
M2 in progress; M3 (claim detection) not started.

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
- [ ] User review/merge and local transcription trial.


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
Next: M3, check-worthy claim detection (not started).
