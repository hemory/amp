#!/bin/bash
# Copilot CLI adapter for Amp session-end hook
# Reads JSON from stdin: {"timestamp":..., "cwd":..., "reason":"complete"}

INPUT=$(cat)

CWD=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.loads(sys.stdin.read())
    print(data.get('cwd', ''))
except Exception:
    print('')
" 2>/dev/null)

if [[ -z "$CWD" ]]; then
    CWD="$(pwd)"
fi

export CLAUDE_PROJECT_DIR="$CWD"

# The original session-end.sh expects a transcript path as $1
# Copilot CLI doesn't provide transcripts, so we pass empty
if [[ -f "$CWD/.claude/hooks/session-end.sh" ]]; then
    bash "$CWD/.claude/hooks/session-end.sh" ""
fi
