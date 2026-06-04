#!/usr/bin/env bash
set -euo pipefail

# ===========================================
# Amp - Install/Uninstall LaunchAgents
# Enables automated Slack briefings on macOS
# ===========================================

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

VAULT_PATH="$(cd "$(dirname "$0")/../.." && pwd)"
PLIST_DIR="$VAULT_PATH/scripts/launchagents"
LAUNCH_DIR="$HOME/Library/LaunchAgents"

AGENTS=(
    "com.amp.morning-brief"
    "com.amp.eod-digest"
    "com.amp.meeting-prep"
)

install_agents() {
    echo -e "${BOLD}Installing Amp LaunchAgents...${NC}"
    echo ""
    mkdir -p "$LAUNCH_DIR"

    for agent in "${AGENTS[@]}"; do
        SRC="$PLIST_DIR/${agent}.plist"
        DEST="$LAUNCH_DIR/${agent}.plist"

        if [ ! -f "$SRC" ]; then
            echo -e "${RED}  ✗ Template not found: $SRC${NC}"
            continue
        fi

        # Substitute VAULT_PATH
        sed "s|{{VAULT_PATH}}|${VAULT_PATH}|g" "$SRC" > "$DEST"

        # Load the agent
        launchctl unload "$DEST" 2>/dev/null || true
        launchctl load "$DEST"
        echo -e "${GREEN}  ✓ $agent installed and loaded${NC}"
    done

    echo ""
    echo -e "${GREEN}${BOLD}Automation active:${NC}"
    echo "  Morning brief:  8:00 AM weekdays"
    echo "  Meeting prep:   Every 30 minutes"
    echo "  EOD digest:     5:00 PM weekdays"
    echo ""
    echo "Requires Slack bot tokens in .env. See docs/integrations.md"
}

uninstall_agents() {
    echo -e "${BOLD}Removing Amp LaunchAgents...${NC}"
    echo ""

    for agent in "${AGENTS[@]}"; do
        DEST="$LAUNCH_DIR/${agent}.plist"
        if [ -f "$DEST" ]; then
            launchctl unload "$DEST" 2>/dev/null || true
            rm -f "$DEST"
            echo -e "${GREEN}  ✓ $agent removed${NC}"
        else
            echo -e "${YELLOW}  - $agent not installed${NC}"
        fi
    done

    echo ""
    echo -e "${GREEN}Automation disabled.${NC}"
}

case "${1:-}" in
    install)
        install_agents
        ;;
    uninstall|remove)
        uninstall_agents
        ;;
    *)
        echo "Usage: $0 [install|uninstall]"
        echo ""
        echo "  install    - Enable automated Slack briefings"
        echo "  uninstall  - Disable automated Slack briefings"
        exit 1
        ;;
esac
