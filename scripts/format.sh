#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "🎨 Formatting codebase..."

# 1. Format and fix Python code via Ruff
if [ -f ".venv/bin/ruff" ]; then
    RUFF_BIN=".venv/bin/ruff"
elif command -v ruff >/dev/null 2>&1; then
    RUFF_BIN="ruff"
else
    RUFF_BIN=""
fi

if [ -n "$RUFF_BIN" ]; then
    echo "  • Formatting Python with Ruff..."
    "$RUFF_BIN" format .
    "$RUFF_BIN" check --fix .
fi

# 2. Format Markdown & JSON via Prettier
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
    echo "  • Formatting Markdown & JSON with Prettier..."
    $PRETTIER_BIN --write "**/*.{md,json,yaml,yml}"
fi

echo "✅ All files formatted successfully!"
