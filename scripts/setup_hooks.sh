#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

HOOKS_DIR="$PROJECT_ROOT/.git/hooks"

echo "🔧 Setting up Git hooks in $HOOKS_DIR..."
mkdir -p "$HOOKS_DIR"

# Install pre-commit hook
cat << 'EOF' > "$HOOKS_DIR/pre-commit"
#!/usr/bin/env bash
set -e
PROJECT_ROOT="$(git rev-parse --show-toplevel)"
exec "$PROJECT_ROOT/scripts/pre-commit.sh"
EOF
chmod +x "$HOOKS_DIR/pre-commit"

# Install pre-push hook
cat << 'EOF' > "$HOOKS_DIR/pre-push"
#!/usr/bin/env bash
set -e
PROJECT_ROOT="$(git rev-parse --show-toplevel)"
exec "$PROJECT_ROOT/scripts/pre-push.sh"
EOF
chmod +x "$HOOKS_DIR/pre-push"

echo "✅ Git hooks installed successfully (pre-commit, pre-push)!"
