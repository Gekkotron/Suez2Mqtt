#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if docker compose version >/dev/null 2>&1; then
    DC=(docker compose)
else
    DC=(docker-compose)
fi

echo "==> git pull --rebase"
git pull --rebase

echo "==> ${DC[*]} build"
"${DC[@]}" build

echo "==> ${DC[*]} up -d"
"${DC[@]}" up -d

echo "==> Done. Recent logs:"
"${DC[@]}" logs --tail=30
