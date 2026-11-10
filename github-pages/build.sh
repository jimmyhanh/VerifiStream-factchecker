#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Only publish the explicitly selected files.
dest="$(mktemp -d)"
trap 'rm -rf "$dest"' EXIT
mkdir -p "$dest/site"
cp github-pages/{index.html,reader.css,reader.js,workshop.webm,workshop.vtt} "$dest/site/"
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
  sed -i 's|<!-- LIVE_LINK -->|<a href="./dashboard/">Open live dashboard</a>|' "$dest/site/index.html"
  cd - >/dev/null
fi
touch "$dest/site/.nojekyll"
mkdir -p github-pages/out
rm -rf github-pages/out/dashboard
cp -R "$dest/site/." github-pages/out/
