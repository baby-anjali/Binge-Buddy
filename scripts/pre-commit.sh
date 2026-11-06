#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "🛡️  [Pre-Commit Hook] Running automated formatting and lint checks..."

# Run format and lint checks
"$PROJECT_ROOT/scripts/format.sh"
"$PROJECT_ROOT/scripts/lint.sh"

# If git has staged files that were auto-formatted, re-stage them
git update-index --again

echo "✅ Pre-commit validation passed!"
