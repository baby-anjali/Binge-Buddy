#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [ -f ".venv/bin/mypy" ]; then
    MYPY_BIN=".venv/bin/mypy"
else
    MYPY_BIN="mypy"
fi

echo "🔍 Running Typecheck with Mypy..."
"$MYPY_BIN" *.py
echo "✅ Typecheck passed!"
