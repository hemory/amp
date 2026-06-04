#!/bin/bash
# Claude Code SessionStart Hook
# Injects strategic hierarchy and tactical context
# For Amp personal knowledge system

# --- COPILOT CLI COMPAT --- #
# When running under Copilot CLI, CLAUDE_PROJECT_DIR may not be set.
# Fall back to the script's own directory (two levels up from .claude/hooks/).
if [[ -z "$CLAUDE_PROJECT_DIR" ]]; then
    CLAUDE_PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi
# --- END COPILOT CLI COMPAT --- #

CLAUDE_DIR="$CLAUDE_PROJECT_DIR"
PILLARS_FILE="$CLAUDE_DIR/System/pillars.yaml"
QUARTER_GOALS="$CLAUDE_DIR/01-Quarter_Goals/Quarter_Goals.md"
WEEK_PRIORITIES="$CLAUDE_DIR/00-Inbox/Weekly_Plans.md"
TASKS_FILE="$CLAUDE_DIR/03-Tasks/Tasks.md"
LEARNINGS_DIR="$CLAUDE_DIR/06-Resources/Learnings"
MISTAKES_FILE="$LEARNINGS_DIR/Mistake_Patterns.md"
PREFERENCES_FILE="$LEARNINGS_DIR/Working_Preferences.md"
ONBOARDING_MARKER="$CLAUDE_DIR/System/.onboarding-complete"

echo "=== Amp Session Context ==="
echo ""
echo "📅 Today: $(date '+%A, %B %d, %Y')"
echo ""

# Skip background checks during onboarding - nothing to check yet!
if [[ ! -f "$ONBOARDING_MARKER" ]]; then
    echo "⏩ Onboarding in progress - background checks disabled"
    echo ""
fi

# SELF-LEARNING: Run background checks inline (fallback if Launch Agents not installed)
# These are fast checks with interval throttling - only run when needed
if [[ -f "$ONBOARDING_MARKER" ]]; then

    # Check for Claude Code updates (if 24+ hours since last check)
    if [[ -x "$CLAUDE_DIR/.scripts/check-anthropic-changelog.cjs" ]]; then
        node "$CLAUDE_DIR/.scripts/check-anthropic-changelog.cjs" 2>/dev/null &
    fi

    # Check for pending learnings (if not checked today)
    if [[ -x "$CLAUDE_DIR/.scripts/learning-review-prompt.sh" ]]; then
        LAST_LEARNING_CHECK="$CLAUDE_DIR/System/.last-learning-check"
        TODAY=$(date +%Y-%m-%d)
        
        if [[ ! -f "$LAST_LEARNING_CHECK" ]] || [[ "$(cat "$LAST_LEARNING_CHECK")" != "$TODAY" ]]; then
            bash "$CLAUDE_DIR/.scripts/learning-review-prompt.sh" 2>/dev/null &
            echo "$TODAY" > "$LAST_LEARNING_CHECK"
        fi
    fi

    # Build meeting cache (incremental — skips unchanged files)
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -f "$SCRIPT_DIR/meeting-cache-builder.cjs" ]]; then
        node "$SCRIPT_DIR/meeting-cache-builder.cjs" 2>/dev/null &
    fi

    # Wait briefly for checks to complete (but don't block session start)
    sleep 0.1
fi

echo ""

# STRATEGIC HIERARCHY (Top-Down)

# 1. Strategic Pillars
if [[ -f "$PILLARS_FILE" ]]; then
    echo "--- Strategic Pillars ---"
    # Extract pillar names and descriptions
    awk '/^  - id:/{getline; name=$0; getline; desc=$0; gsub(/^[[:space:]]*name: "/, "", name); gsub(/"$/, "", name); gsub(/^[[:space:]]*description: "/, "", desc); gsub(/"$/, "", desc); print "• " name " — " desc}' "$PILLARS_FILE" 2>/dev/null | head -5
    echo "---"
    echo ""
fi

# 2. Quarterly Goals
if [[ -f "$QUARTER_GOALS" ]]; then
    # Check if goals are filled in (not template)
    if ! grep -q "^\[Goal 1 Title\]" "$QUARTER_GOALS" 2>/dev/null; then
        echo "--- Quarter Goals ---"
        # Extract goal titles and progress
        awk '/^### [0-9]\./,/^---$/{if(/^### [0-9]\./) print; if(/^\*\*Progress:\*\*/) print}' "$QUARTER_GOALS" 2>/dev/null | head -10
        echo "---"
        echo ""
    fi
fi

# 3. Weekly Priorities
if [[ -f "$WEEK_PRIORITIES" ]]; then
    # Extract current week's priorities section
    WEEK_PRIORITIES_CONTENT=$(awk '/^## 🎯 This Week|^## This Week/,/^---$/{if(!/^##/ && !/^---/ && NF) print}' "$WEEK_PRIORITIES" 2>/dev/null)
    if [[ -n "$WEEK_PRIORITIES_CONTENT" ]]; then
        echo "--- Weekly Priorities ---"
        echo "$WEEK_PRIORITIES_CONTENT"
        echo "---"
        echo ""
    fi
fi

# TACTICAL CONTEXT

# 4. Urgent Tasks
if [[ -f "$TASKS_FILE" ]]; then
    URGENT=$(grep -i "P0\|urgent\|today\|overdue" "$TASKS_FILE" 2>/dev/null | grep "^\- \[ \]" | head -3)
    if [[ -n "$URGENT" ]]; then
        echo "--- Urgent Tasks ---"
        echo "$URGENT"
        echo "---"
        echo ""
    fi
fi

# 5. Working Preferences
if [[ -f "$PREFERENCES_FILE" ]]; then
    PREF_COUNT=$(grep -c "^### " "$PREFERENCES_FILE" 2>/dev/null || echo "0")
    if [[ "$PREF_COUNT" -gt 0 ]]; then
        echo "--- Working Preferences ---"
        grep -A1 "^### " "$PREFERENCES_FILE" | grep -v "^--$" | head -10
        echo "---"
        echo ""
    fi
fi

# 6. Active Mistake Patterns
if [[ -f "$MISTAKES_FILE" ]]; then
    PATTERN_COUNT=$(grep -c "^### " "$MISTAKES_FILE" 2>/dev/null || echo "0")
    if [[ "$PATTERN_COUNT" -gt 0 ]]; then
        echo "--- Active Mistake Patterns ($PATTERN_COUNT) ---"
        awk '/^## Active Patterns/,/^## Resolved/' "$MISTAKES_FILE" | grep -A2 "^### " | grep -v "^--$" | head -15
        echo "---"
        echo ""
    fi
fi

# 7. Recent Learnings
if [[ -d "$LEARNINGS_DIR" ]]; then
    FOUND_LEARNINGS=0
    for file in "$LEARNINGS_DIR"/*.md; do
        if [[ -f "$file" ]]; then
            filename=$(basename "$file" .md)
            recent=$(grep -E "## .* — 202[0-9]-[0-9]{2}-[0-9]{2}" "$file" 2>/dev/null | tail -2)
            if [[ -n "$recent" ]]; then
                if [[ $FOUND_LEARNINGS -eq 0 ]]; then
                    echo "--- Recent Learnings ---"
                    FOUND_LEARNINGS=1
                fi
                echo "[$filename]"
                echo "$recent"
            fi
        fi
    done
    if [[ $FOUND_LEARNINGS -eq 1 ]]; then
        echo "---"
        echo ""
    fi
fi

# 8. Pending Claude Code Updates
CHANGELOG_PENDING="$CLAUDE_DIR/System/changelog-updates-pending.md"
if [[ -f "$CHANGELOG_PENDING" ]]; then
    echo "--- 🆕 AI Updates Detected ---"
    echo "New features or capabilities available!"
    echo "Run: /amp-whats-new"
    echo "---"
    echo ""
fi

# 9. Pending Learning Reviews
LEARNING_PENDING="$CLAUDE_DIR/System/learning-review-pending.md"
if [[ -f "$LEARNING_PENDING" ]]; then
    # Extract count from the file
    LEARNING_COUNT=$(grep "^\*\*Count:\*\*" "$LEARNING_PENDING" 2>/dev/null | sed 's/.*Count:\*\* \([0-9]*\).*/\1/')
    if [[ -n "$LEARNING_COUNT" ]]; then
        echo "--- 📚 Pending Learnings Review ($LEARNING_COUNT) ---"
        echo "Session learnings ready for review"
        echo "Run: /amp-whats-new --learnings"
        echo "---"
        echo ""
    fi
fi

# 10. New Vault Welcome (if < 7 days old and Phase 2 not completed)
ONBOARDING_MARKER="$CLAUDE_DIR/System/.onboarding-complete"
if [[ -f "$ONBOARDING_MARKER" ]]; then
    # Check if marker is less than 7 days old
    AGE_CHECK=$(find "$ONBOARDING_MARKER" -mtime -7 2>/dev/null)
    if [[ -n "$AGE_CHECK" ]]; then
        # Check if phase2_completed is false
        PHASE2_DONE=$(grep '"phase2_completed": true' "$ONBOARDING_MARKER" 2>/dev/null)
        if [[ -z "$PHASE2_DONE" ]]; then
            echo "--- 👋 Welcome! ---"
            echo "You're probably wondering what to do next..."
            echo "Try: /getting-started"
            echo "---"
            echo ""
        fi
    fi
fi

# 11. Amp Health System — Pre-flight checks and error queue
# Runs preflight health checks (MCP servers, config files, etc.) and displays
# any queued errors. Silent when everything is healthy (no output = no display).
if [[ -f "$ONBOARDING_MARKER" ]]; then
    AMP_CORE_DIR="$CLAUDE_DIR/amp-core"
    if [[ -f "$AMP_CORE_DIR/core/utils/preflight.py" ]]; then
        HEALTH_OUTPUT=$(cd "$AMP_CORE_DIR" && python3 -c "
import sys
sys.path.insert(0, '.')
from core.utils.preflight import run_preflight, format_output, format_errors
health = run_preflight()
preflight = format_output(health)
errors = format_errors()
if preflight:
    print(preflight)
if errors:
    print(errors)
" 2>/dev/null)
        if [[ -n "$HEALTH_OUTPUT" ]]; then
            echo "$HEALTH_OUTPUT"
        fi
    fi
fi

echo "=== End Session Context ==="
