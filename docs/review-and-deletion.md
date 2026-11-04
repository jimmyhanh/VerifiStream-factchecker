# Reviewed propositions and video deletion — November 4, 2026

## Plan

Complex spoken statements currently abstain under the conservative English grammar.
Add an explicit review workflow before the next milestone: optional structured AI
suggestions and a no-key manual editor, always showing the original candidate. Drafts
cannot be searched. Approval creates a new immutable decomposition with exact source
quote/timestamps, a user-reviewed transformation, recorded request and optional draft
snapshot. Conditions, attribution, negation, quantities and timing must be preserved;
structural validation and human approval are not proof of semantic faithfulness.
The original transcript, old decompositions and historical hashes stay unchanged.
No new default fields may alter serialization of historical nested snapshots.

New endpoints: POST/list/get proposition-drafts, POST reviewed-decompositions.
Drafts use a replaceable provider and existing bounded HTTPS transport. Model setting
DECOMPOSITION_MODEL defaults to MAPPING_MODEL if empty; keys remain server-side.
Limit each suggestion request to ten candidates, each at most 4000 characters,
and each approval to thirty propositions across ten candidates. No automatic AI calls,
retries, or paid trial. Provider/model/prompt/usage and original claim snapshots persist.
Human approval explicitly acknowledges checking meaning. Reviewed propositions are
interpretations; evidence verification must still use retrieved sources.

Add DELETE /videos/{id} and DELETE /videos, with an explicit clear confirmation body
and a preview inventory of IDs. Reject clear if the inventory changed since preview.
Browser confirms the selected filename or exact all-video count and explains that
media, transcripts and downstream runs are removed. Only metadata-backed UUID video
folders are targeted; model cache and unrelated folders remain. A process-local
activity gate excludes deletion from active video requests, including uploads.
This is a local single-process contract, not distributed locking or authentication.
Deletion first moves each video into an internal tombstone directory, then purges it.
Report incomplete disk cleanup explicitly; clear retries old tombstones. Never claim
an interrupted cleanup reclaimed disk space. Test only temporary fixture videos.

## Validation plan

Regression tests for snapshot compatibility, condition-preserving review provenance,
draft parsing/failure/lineage, unapproved drafts not searchable, and a full reviewed
claim -> retrieval -> mapping -> confidence chain. Deletion tests cover all associated
files, model-cache preservation, missing IDs, changed inventories, cancellation UI,
concurrent active operations and cleanup failures. Browser tests cover manual review,
AI draft editing/approval and delete/clear confirmations. Run full backend and frontend
CI; record observed results and any remaining acceptance limits below.

## Implementation and local results

Implemented the proposed interfaces and dashboard controls. Backend: **301 passed,
1 skipped** (optional real-ASR fixture unavailable locally). Frontend TypeScript and
production build passed. Browser workflow tests are included for manual/AI approval,
acknowledgement reset after edits, retrieval, and cancel/confirm deletion; CI executes
these against synthetic providers. No real paid AI request was performed.

Set optional `DECOMPOSITION_MODEL` and `OPENAI_API_KEY` in `.env`, then run
`docker compose up --build -d`. Manual review works without those settings.
Use Review propositions on the Claims tab, approve, then select the resulting atomic
propositions for evidence retrieval. Keep conditions and attribution in their wording.

Limits: 75 words/600 characters per proposition; AI suggestions are not guaranteed
faithful and require human review. Local approvals are not authenticated identities.
Deletion is permanent and limited to a single application process. A clear operation
that encounters a filesystem rename error may have deleted earlier entries; the UI
refreshes the inventory, and the operation does not roll back those deletions.

Remote validation: PR #12 is draft. GitHub has not started a workflow for this
branch as of this update, so browser and Docker acceptance remain unverified.
The tests are committed; run the Backend tests workflow on this branch before merging.
