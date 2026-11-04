# Milestone 11: durable background jobs — implementation plan

First increment: local, bounded single-worker queue behind a job service; immutable
stage runs remain the authoritative outputs. Persist jobs beneath each video so normal
deletions remove job history. Acquire an OS file lock for the worker; do not run multiple
API workers against JSON storage. Queue survives restart. Running jobs become interrupted
and require an explicit retry; never silently replay potentially billable calls.

Jobs carry UUID idempotency keys, validated action input, status, timestamps, current
stage and checkpoint run IDs. Reusing a key returns the original job; changing its input
is a conflict. This is request deduplication, not a semantic/freshness cache. Analyze video
runs transcription, claim detection and decomposition with checkpoints, then pauses for
claim review. Findings jobs rank, verify and calculate confidence with checkpoints.
Single-stage jobs support existing stage adapters. Queue bound: 100 pending jobs.
Queued cancellation is safe; running cancellation is not promised. Retry preserves
successful checkpoints and creates a new attempt record. Deletion is blocked while
jobs are queued or running. Public progress exposes IDs/errors, not secrets.

Frontend shows persisted progress and allows refresh while backend work continues.
Keep existing synchronous APIs and manual workflow compatible. Upload transfer and
FFmpeg extraction remain synchronous in this increment. No WebSocket, Redis, external
worker, cross-process scaling, semantic result cache or live video yet. Those remain
Milestone 11 follow-ups; this increment must not be described as full scalability.

Validation: idempotency conflicts, queue limits, recovery, cancellation, sanitized
failure, checkpoint retry, deletion exclusion, and real API integration with fake
providers; browser refresh/progress test; full regression and Docker CI.
