# VerifiStream architecture

## Principles
A modular monolith with replaceable adapters. Verification must use retrieved evidence, never model memory alone. No political or ideological bias scores. Compound statements become atomic propositions, including separate causal propositions. Evidence relationships are SUPPORTS, CONTRADICTS, QUALIFIES, CONTEXT, IRRELEVANT. Future statuses: Supported, Partially Supported, Contradicted, Conflicting Evidence, Insufficient Evidence. Evidence Confidence is a versioned evidence-strength score, not a probability of truth.

## Milestone 1 implementation plan
1. Establish project/configuration and Pydantic schemas.
2. Implement local storage and persistent metadata behind protocols.
3. Implement FFprobe validation and FFmpeg extraction behind a media protocol.
4. Expose health, multipart upload, and UUID status endpoints.
5. Test validation, failure cleanup, persistence, and real audio extraction.
6. Add container/CI configuration and exact development instructions.
Only upload and audio extraction are implemented in this milestone.

## Boundaries
- api: HTTP parsing, request limits, error mapping.
- videos: orchestration and processing lifecycle.
- storage: local file adapter behind VideoStorage.
- database: metadata repository protocol and local JSON development adapter.
- media: MediaProcessor protocol, FFprobe/FFmpeg adapter.
- models/shared: schemas, configuration, typed errors, JSON logging.
- Future transcription, claims, retrieval, evidence, verification, confidence: separate packages, introduced at their milestones.
No frontend, AI provider, transcription, or search dependencies in M1.

## Milestone 1 choices
Use atomic local JSON metadata behind a repository interface to keep initial development dependency-light. PostgreSQL replaces this adapter before multi-process/job scaling; this is an explicit deferral of the target database, not a production persistence design.
Each request gets a UUID directory with original media, extracted WAV, and metadata.
Untrusted filenames never become filesystem paths.
Enforce request bytes before multipart parsing and count actual file bytes while storing.
Allow MP4/MOV, WebM and Matroska; extension and MIME are preliminary checks. FFprobe must identify an allowed container, video stream, audio stream, and bounded positive duration.
Run FFmpeg without a shell, restrict input protocols/demuxers, impose timeout and output-size bounds, write temporary output, then rename.
Extract the first audio track into mono 16 kHz signed 16-bit PCM WAV.
Persist SHA-256, UTC timestamps, adapter version, FFmpeg version, and extraction parameters.
POST waits for extraction (bounded concurrency); GET returns persisted state. This is synchronous processing, not a durable background job. Restart during processing can leave an interrupted record; no automatic retry in M1.
Statuses: processing -> completed or failed. Invalid uploads are rejected and removed. Processing failures retain metadata and original input for diagnosis but remove partial audio.
API is intended for local development, bound to localhost. Authentication, quotas, retention and sandboxed worker isolation are prerequisites for public deployment.

## Future scalability and reproducibility
Introduce PostgreSQL migrations and durable jobs; use stage-specific tasks with idempotency keys, leases, retries, attempt records, and object-storage references. The same service interfaces can be invoked by transcription, extraction, retrieval and verification workers independently. API replicas will not hold jobs in memory. Add Redis/caching only with measured need.
Verification runs are append-only: preserve model/provider version, prompt version, retrieval version, confidence version, timestamp, immutable evidence snapshot and content hash. Algorithm changes create a new run.
Evidence stores URL, publisher, title, publication date (nullable when unknown), source type, primary/secondary classification, passage and offsets, retrieval time, relevance and directness. Map each passage to an atomic proposition. Track original-report provenance/independence clusters so syndicated copies do not count as independent confirmation.
Confidence is a deterministic tested module separate from the LLM relationship/verdict adapter, exposing signal contributions and algorithm version. Calibrate later against held-out labeled evaluation data.
