#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "🔎 Checking code standards and linting..."

# 1. Check Python linting and formatting via Ruff
if [ -f ".venv/bin/ruff" ]; then
    RUFF_BIN=".venv/bin/ruff"
elif command -v ruff >/dev/null 2>&1; then
    RUFF_BIN="ruff"
else
    RUFF_BIN=""
fi

if [ -n "$RUFF_BIN" ]; then
    echo "  • Checking Python with Ruff..."
    "$RUFF_BIN" check .
    "$RUFF_BIN" format --check .
fi

# 2. Check Prettier formatting
if [ -f "node_modules/.bin/prettier" ]; then
    PRETTIER_BIN="node_modules/.bin/prettier"
elif command -v prettier >/dev/null 2>&1; then
    PRETTIER_BIN="prettier"
elif command -v npx >/dev/null 2>&1; then
    PRETTIER_BIN="npx prettier"
else
    PRETTIER_BIN=""
fi

if [ -n "$PRETTIER_BIN" ]; then
    echo "  • Checking Prettier style..."
    $PRETTIER_BIN --check "**/*.{md,json,yaml,yml}"
fi

echo "✅ All lint and style checks passed!"
