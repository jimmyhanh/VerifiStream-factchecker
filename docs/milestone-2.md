# Milestone 2 plan

Scope: saved audio -> timestamped transcript, without claim extraction or verification.

1. Add validated segment, transcript result and run schemas.
2. Add provider and transcript repository protocols with local adapters.
3. Run Faster Whisper CPU/int8 in a bounded subprocess, so timeout terminates inference.
4. Cache model downloads; record resolved model revision, provider/package versions,
   parameters, input audio hash and elapsed time. Retain all runs.
5. Add POST /videos/{id}/transcriptions, GET /videos/{id}/transcriptions,
   GET /videos/{id}/transcriptions/{run_id}, GET /videos/{id}/transcript (latest successful).
6. Add API/schema/adapter/timeout tests and an opt-in real speech smoke test.
7. Update Docker, README, CI and progress, preserving the existing media volume.

POST is synchronous for this milestone; one transcription at a time per API process.
GET remains responsive. Busy requests receive 503; retries create a new run.
Failures are recorded with safe error codes. Silence yields an empty transcript,
not invented text. ASR can still mishear/hallucinate; output is not evidence.
No speaker diarization, word alignment, live stream or durable job queue yet.
First download needs internet; subsequent cached inference stays local.
