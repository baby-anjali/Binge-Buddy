#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "🚀 [Pre-Push Hook] Running validation suite before pushing..."

# 1. Run typecheck
"$PROJECT_ROOT/scripts/typecheck.sh"

# 2. Run test suite
"$PROJECT_ROOT/scripts/test.sh"

echo "✅ Pre-push validation passed! Safe to push."
