#!/usr/bin/env bash
# Build the React frontend and place the output inside the FastAPI static/ folder
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/../apps/social-analyzer/frontend"

echo "=== Building Danone Social Analyzer frontend ==="
cd "$FRONTEND_DIR"

if ! command -v node &>/dev/null; then
  echo "ERROR: Node.js is required. Install via https://nodejs.org"
  exit 1
fi

echo "--- Installing npm dependencies ---"
npm install

echo "--- Building production bundle ---"
npm run build

echo "=== Build complete. Static files in apps/social-analyzer/backend/static/ ==="
