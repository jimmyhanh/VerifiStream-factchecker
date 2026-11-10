# VerifiStream for GitHub Pages
The default edition opens completed verification and confidence JSON runs locally. The bundled sample uses fictional evidence. To export a run, use the download control in the original dashboard's Findings tab.

## Publish
Select **Settings → Pages → Build and deployment → Source → GitHub Actions**. Merge the Pages edition into main. The **Publish VerifiStream Pages** workflow publishes the site. You can also run it manually from Actions.

## Live dashboard
To include upload, transcription, retrieval, and verification, supply the HTTPS URL of a separately hosted VerifiStream API in **Settings → Secrets and variables → Actions → Variables → PAGES_API_URL**. Add the exact Pages origin (e.g. `https://jimmyhanh.github.io`) to the backend’s `CORS_ORIGINS` and rerun the workflow. The dashboard sends API requests from the visitor's browser. Use an access-controlled backend suited to your audience before enabling writes. CORS alone allows no user authentication. Keep model and search keys on the server.

## Local preview
Run `bash github-pages/build.sh`, then `python -m http.server 8080 --directory github-pages/out`. Open http://localhost:8080. For a local live build, set NEXT_PUBLIC_API_BASE_URL to your HTTPS endpoint and use Node 24. The build takes the frontend from the current commit.
