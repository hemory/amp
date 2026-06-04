#!/bin/bash
# Copilot CLI adapter for Amp safety guard
# Translates Copilot CLI preToolUse JSON → Claude Code format → calls original guard
#
# Accepts the payload shapes Copilot CLI has used over time:
#   Shape A: {"toolName":"bash","toolArgs":"{\"command\":\"rm -rf /\"}"}
#   Shape B: {"tool_name":"bash","tool_args":{"command":"rm -rf /"}}
#   Shape C: {"tool":"bash","args":{...}}
# Original guard expects: {"tool_name":"bash","tool_input":{"command":"rm -rf /"}}
# Original guard: exit 2 = block. Copilot CLI: {"permissionDecision":"deny"} = block

INPUT=$(cat)

# Normalize Copilot CLI format to Claude Code format.
NORMALIZED=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.loads(sys.stdin.read())
    tool_name = data.get('toolName') or data.get('tool_name') or data.get('tool') or ''
    raw_args = data.get('toolArgs')
    if raw_args is None:
        raw_args = data.get('tool_args')
    if raw_args is None:
        raw_args = data.get('args')
    if raw_args is None:
        raw_args = {}
    if isinstance(raw_args, str):
        try:
            tool_input = json.loads(raw_args)
        except Exception:
            tool_input = {'raw': raw_args}
    elif isinstance(raw_args, dict):
        tool_input = raw_args
    elif isinstance(raw_args, list):
        tool_input = {'argv': raw_args}
    else:
        tool_input = {}
    print(json.dumps({'tool_name': tool_name, 'tool_input': tool_input}))
except Exception:
    print(json.dumps({}))
" 2>/dev/null)

# Call the original safety guard with Claude-format input
RESULT=$(echo "$NORMALIZED" | bash .claude/hooks/amp-safety-guard.sh 2>&1)
EXIT_CODE=$?

# If exit code 2 (Claude Code block signal), output Copilot CLI deny format
if [[ $EXIT_CODE -eq 2 ]]; then
    echo "$RESULT" | head -1 | python3 -c "
import sys, json
reason = sys.stdin.read().strip()
print(json.dumps({'permissionDecision':'deny','permissionDecisionReason':reason}))
"
    exit 0
fi

# Allow by default
exit 0
