# Milestone 10 — Dashboard implementation plan

## Scope and architecture

Build a Next.js / React / TypeScript dashboard in `frontend/`, served on port 3000.
The browser calls the existing FastAPI service directly on port 8000, avoiding a
second proxy buffer/timeout for large uploads and synchronous transcription.
`NEXT_PUBLIC_API_BASE_URL` contains only the public backend address; provider keys
stay on the backend. Exact CORS origins default to localhost/127.0.0.1:3000; no
wildcard origins or credentials. Both Compose ports remain loopback-bound.

Add a paginated GET /videos library endpoint and a typed GET /configuration response
containing only upload size/duration limits. No workflow or confidence rules change.
Local JSON listing scans metadata before pagination; PostgreSQL indexing is M11.

## User workflow

1. Upload a supported video, see pending extraction and actual completion/failure.
2. Open a saved video without copying UUIDs; run transcription and inspect timestamps.
3. Detect candidates, select up to 100, decompose, inspect needs-review reasons.
4. Select 1–3 atomic propositions, add explicitly unverified context when needed;
   choose Brave search or 1–5 public HTTPS URLs per selected proposition.
5. Inspect source metadata/passages and per-proposition retrieval errors; select
   1–12 passages to map. Clearly indicate the external model call before execution.
6. Inspect relationships, quotes, review/errors, then rank, verify and score.
7. Show statuses per atomic proposition, exact citations and disagreements, selected
   evidence coverage, source dependence, and experimental confidence breakdown/caps.

Persisted API histories are authoritative. Stage selectors restore matching ancestry;
changing a stage clears downstream selections. Never combine confidence from one
verification with another. Keep requests single-flight, prevent duplicate submission,
show explicit loading/empty/error states and provide refresh after uncertain network
outcomes. No automatic retry of paid or mutating requests. No simulated progress or
live claim. A running request can survive a browser disconnect on the backend;
refresh reads saved runs without resubmission.

## Design and validation

Use a restrained navy/teal workspace, light document surfaces, text-labelled status
badges, a numbered workflow, selectable transcript/claim/evidence cards and a saved
video sidebar. Responsive layout, labelled controls, visible keyboard focus, no
color-only meaning, no rendered source HTML or unsafe citation URL schemes.
No decorative charts or synthetic results in the production application.

Test backend pagination/config/CORS, frontend build/type checking, and Playwright
browser flows with explicit synthetic fixtures from the actual backend adapters.
Test selection limits, network/failed-run errors, history ancestry, confidence/citation
rendering and mobile layout. CI builds Compose and checks the dashboard. Live paid
provider accuracy and production scaling are outside M10; no public deployment.


## Observed validation — October 30, 2026

Implementation `face635d35d800b2448eedb3c60693af22a9c42c` passed
[CI run 41125543529](https://github.com/jimmyhanh/VerifiStream-factchecker/actions/runs/41125543529):
281 backend tests (16.17 seconds), 10 frontend checks (9.5 seconds), production
Next build/TypeScript, Docker build/start for both services, dashboard HTTP content
and existing real-media/transcription/claim/decomposition container checks.
Desktop/mobile screenshots and reports are saved in `dashboard-browser-tests`.

Local backend results were 280 passed with one opt-in real-ASR skip. Managed local
preview supplied incompatible Vite flags to Next.js, so local browser/manual visual
review was unavailable; standard-server Chromium workflow checks passed in CI.
All browser provider inputs are explicitly synthetic; real provider accuracy and
confidence calibration are not measured by these tests.

## Run and acceptance rehearsal

```sh
git fetch origin
git switch milestone-10-dashboard
git pull
docker compose up --build -d --force-recreate
```

Open http://localhost:3000. Preserve existing `.env` provider values and the `media`
volume. The dashboard adds no AI key. Upload a short English video, transcribe,
select candidates/propositions, retrieve and select passages, map, rank, verify,
and calculate confidence. Reopen the saved video and inspect an older run to rehearse
history handling. Manual HTTPS source URLs can be used without Brave search.

Remaining limits: local unauthenticated single-user use, synchronous requests,
full nested run histories, JSON metadata scans, no player/seeking, no editing of
heuristic propositions or custom ranking annotations. Real-video provider rehearsal
is still needed. M11 jobs/caching and M12 live input are not included.
