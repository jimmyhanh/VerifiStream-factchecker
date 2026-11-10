#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Only publish the explicitly selected files.
dest="$(mktemp -d)"
trap 'rm -rf "$dest"' EXIT
mkdir -p "$dest/site"
cp github-pages/{index.html,reports.html,config.js,video.js,reader.css,reader.js} "$dest/site/"
if [[ -n "${NEXT_PUBLIC_API_BASE_URL:-}" ]]; then
  [[ "$NEXT_PUBLIC_API_BASE_URL" == https://* ]] || { echo "Set an HTTPS API URL"; exit 1; }
  mkdir "$dest/frontend"
  git archive HEAD frontend | tar -x -C "$dest"
  cd "$dest/frontend"
  cp "$OLDPWD/github-pages/next.config.ts" .
  git apply "$OLDPWD/github-pages/navigation.patch"
  export PAGES_DASHBOARD_PATH="${PAGES_BASE_PATH:-}/dashboard"
  npm ci --no-audit --no-fund
  npm run build
  cp -R out "$dest/site/dashboard"
  node -e 'const fs = require("node:fs"); const url = new URL(process.env.NEXT_PUBLIC_API_BASE_URL); if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash) throw Error("Expected a public HTTPS API base URL"); fs.writeFileSync(process.argv[1], "window.verifiStreamApi = " + JSON.stringify(url.href.replace(/\/+$/, "")) + ";\n")' "$dest/site/config.js"
  cd - >/dev/null
fi
touch "$dest/site/.nojekyll"
mkdir -p github-pages/out
rm -rf github-pages/out/dashboard
cp -R "$dest/site/." github-pages/out/
