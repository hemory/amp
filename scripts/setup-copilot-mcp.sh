#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python3"
WITH_ONBOARDING=false
REMOVE_ONBOARDING=false

usage() {
  cat <<'EOF'
Usage: scripts/setup-copilot-mcp.sh [--with-onboarding] [--remove-onboarding]

Registers Amp MCP servers in Copilot CLI user-level config.

Options:
  --with-onboarding   Also register amp-onboarding for first-time /setup.
  --remove-onboarding Remove amp-onboarding after onboarding is complete.
  -h, --help          Show this help.
EOF
}

for arg in "$@"; do
  case "$arg" in
    --with-onboarding)
      WITH_ONBOARDING=true
      ;;
    --remove-onboarding)
      REMOVE_ONBOARDING=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      usage >&2
      exit 64
      ;;
  esac
done

if ! command -v copilot >/dev/null 2>&1; then
  echo "Copilot CLI was not found on PATH. Install Copilot CLI before configuring Amp MCP servers." >&2
  exit 1
fi

if [ "$REMOVE_ONBOARDING" = true ] && [ "$WITH_ONBOARDING" = false ]; then
  copilot mcp remove amp-onboarding >/dev/null 2>&1 || true
  echo "Removed amp-onboarding from Copilot CLI user MCP config."
  exit 0
fi

if [ ! -x "$PYTHON" ]; then
  echo "Amp virtualenv not found at $PYTHON. Run ./install.sh first." >&2
  exit 1
fi

add_server() {
  local name="$1"
  local script="$2"

  copilot mcp remove "$name" >/dev/null 2>&1 || true
  copilot mcp add "$name" \
    --env "VAULT_PATH=$ROOT" \
    --env "PYTHONPATH=$ROOT" \
    -- "$PYTHON" "$ROOT/$script"
}

add_server amp-work core/mcp/work_server.py
add_server amp-improvements core/mcp/improvements_server.py
add_server session-memory core/mcp/session_memory_server.py

if [ "$WITH_ONBOARDING" = true ]; then
  add_server amp-onboarding core/mcp/onboarding_server.py
fi

cat <<'EOF'

Amp MCP servers configured for Copilot CLI:
  - amp-work
  - amp-improvements
  - session-memory
EOF

if [ "$WITH_ONBOARDING" = true ]; then
  cat <<'EOF'
  - amp-onboarding (temporary setup-only server)
EOF
fi

cat <<'EOF'

Workspace .mcp.json is intentionally kept empty. Copilot CLI will load these
from your user MCP config instead of auto-starting repo-local workspace MCPs.
Restart Copilot CLI to use the new tools.
EOF

if [ "$WITH_ONBOARDING" = true ]; then
  cat <<'EOF'

After /setup is complete, remove the temporary onboarding server:
  scripts/setup-copilot-mcp.sh --remove-onboarding
EOF
fi
