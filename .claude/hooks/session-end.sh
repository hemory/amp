#!/bin/bash
# Claude Code / Copilot CLI SessionEnd Hook
# Logs session end timestamp for tracking (with deduplication)
# For Amp personal knowledge system

# --- COPILOT CLI COMPAT --- #
if [[ -z "$CLAUDE_PROJECT_DIR" ]]; then
    CLAUDE_PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi
# --- END COPILOT CLI COMPAT --- #

CLAUDE_DIR="$CLAUDE_PROJECT_DIR"
SESSION_LEARNINGS_DIR="$CLAUDE_DIR/System/Session_Learnings"
TRANSCRIPT_PATH="$1"

mkdir -p "$SESSION_LEARNINGS_DIR"

TODAY=$(date +%Y-%m-%d)
LEARNING_FILE="$SESSION_LEARNINGS_DIR/$TODAY.md"

# --- DEDUPLICATION: Skip if last entry was less than 5 minutes ago --- #
if [[ -f "$LEARNING_FILE" ]]; then
    LAST_TIMESTAMP=$(grep -oE '^## [0-9]{2}:[0-9]{2}' "$LEARNING_FILE" | tail -1 | sed 's/## //')
    if [[ -n "$LAST_TIMESTAMP" ]]; then
        NOW_MINUTES=$(( $(date +%H) * 60 + $(date +%M) ))
        LAST_H=$(echo "$LAST_TIMESTAMP" | cut -d: -f1 | sed 's/^0//')
        LAST_M=$(echo "$LAST_TIMESTAMP" | cut -d: -f2 | sed 's/^0//')
        LAST_MINUTES=$(( LAST_H * 60 + LAST_M ))
        DIFF=$(( NOW_MINUTES - LAST_MINUTES ))
        if [[ $DIFF -ge 0 ]] && [[ $DIFF -lt 5 ]]; then
            # Last entry was less than 5 minutes ago, skip to avoid spam
            exit 0
        fi
    fi
fi

# Create file with header if it doesn't exist yet
if [[ ! -f "$LEARNING_FILE" ]]; then
    cat > "$LEARNING_FILE" <<EOF
# Session Learnings - $TODAY

Automatically captured from sessions.

---

EOF
fi

# Log session end (actual learning extraction happens via /daily-review)
echo "## $(date +%H:%M) - Session completed" >> "$LEARNING_FILE"
echo "" >> "$LEARNING_FILE"
echo "**Session ended**" >> "$LEARNING_FILE"
if [[ -n "$TRANSCRIPT_PATH" ]] && [[ -f "$TRANSCRIPT_PATH" ]]; then
    echo "**Transcript:** \`$TRANSCRIPT_PATH\`" >> "$LEARNING_FILE"
fi
echo "" >> "$LEARNING_FILE"
echo "_Run /daily-review to extract learnings from this session._" >> "$LEARNING_FILE"
echo "" >> "$LEARNING_FILE"
echo "---" >> "$LEARNING_FILE"
echo "" >> "$LEARNING_FILE"

exit 0
