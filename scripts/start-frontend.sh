#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/frontend"

if [ ! -d "node_modules" ]; then
  npm install --no-audit --no-fund
fi

exec npm run dev
