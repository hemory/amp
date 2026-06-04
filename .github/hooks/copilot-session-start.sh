#!/bin/bash
# Copilot CLI adapter for Amp session-start hook
# Reads JSON from stdin (Copilot CLI format), sets env vars, calls original script
#
# Copilot CLI sends: {"timestamp":..., "cwd":"/path/to/amp", "source":"new", "initialPrompt":"..."}
# Original script expects: $CLAUDE_PROJECT_DIR environment variable

INPUT=$(cat)

# Extract cwd from Copilot CLI JSON input
CWD=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.loads(sys.stdin.read())
    print(data.get('cwd', ''))
except Exception:
    print('')
" 2>/dev/null)

# Fall back to current directory if parsing fails
if [[ -z "$CWD" ]]; then
    CWD="$(pwd)"
fi

# Set the env var that the original Amp hooks expect
export CLAUDE_PROJECT_DIR="$CWD"

# Run the original session-start hook
if [[ -f "$CWD/.claude/hooks/session-start.sh" ]]; then
    bash "$CWD/.claude/hooks/session-start.sh"
fi
