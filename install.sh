#!/usr/bin/env bash
set -euo pipefail

# ===========================================
# Amp — Your AI Chief of Staff. Your work, amplified.
# One-command installer
# ===========================================

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

VAULT_PATH="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo -e "${CYAN}${BOLD}⚡ Amp — Your AI Chief of Staff. Your work, amplified.${NC}"
echo -e "${CYAN}   Install in 10 minutes. Ready by lunch.${NC}"
echo ""

# -------------------------------------------
# Step 1: Check prerequisites
# -------------------------------------------
echo -e "${BOLD}[1/6] Checking prerequisites...${NC}"

MISSING=()

if ! command -v git &> /dev/null; then
    MISSING+=("git")
fi

if ! command -v node &> /dev/null; then
    MISSING+=("node (Node.js 18+)")
else
    NODE_VERSION=$(node -v | sed 's/v//' | cut -d. -f1)
    if [ "$NODE_VERSION" -lt 18 ]; then
        echo -e "${RED}  ✗ Node.js version $(node -v) found, need 18+${NC}"
        MISSING+=("node (18+)")
    else
        echo -e "${GREEN}  ✓ Node.js $(node -v)${NC}"
    fi
fi

if ! command -v python3 &> /dev/null; then
    MISSING+=("python3 (3.10+)")
else
    PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
    if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
        echo -e "${RED}  ✗ Python $PY_VERSION found, need 3.10+${NC}"
        MISSING+=("python3 (3.10+)")
    else
        echo -e "${GREEN}  ✓ Python $PY_VERSION${NC}"
    fi
fi

if [ ${#MISSING[@]} -gt 0 ]; then
    echo ""
    echo -e "${RED}Missing prerequisites:${NC}"
    for item in "${MISSING[@]}"; do
        echo -e "  ${RED}✗ $item${NC}"
    done
    echo ""
    echo "Install these and run ./install.sh again."
    exit 1
fi

echo -e "${GREEN}  ✓ git $(git --version | cut -d' ' -f3)${NC}"

# -------------------------------------------
# Step 2: Install Node.js dependencies
# -------------------------------------------
echo ""
echo -e "${BOLD}[2/6] Installing Node.js dependencies...${NC}"
npm install --quiet 2>&1 | tail -1
echo -e "${GREEN}  ✓ Node modules installed${NC}"

# -------------------------------------------
# Step 3: Set up Python virtual environment
# -------------------------------------------
echo ""
echo -e "${BOLD}[3/6] Setting up Python environment...${NC}"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo -e "${GREEN}  ✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}  ✓ Virtual environment exists${NC}"
fi

source .venv/bin/activate
pip install -q -r requirements.txt 2>&1 | tail -1
echo -e "${GREEN}  ✓ Python dependencies installed${NC}"

# -------------------------------------------
# Step 4: Configure safe workspace MCP defaults
# -------------------------------------------
echo ""
echo -e "${BOLD}[4/6] Configuring MCP servers...${NC}"
if [ ! -f ".mcp.json" ]; then
    cp .mcp.json.template .mcp.json
    echo -e "${GREEN}  ✓ .mcp.json created with workspace MCP auto-start disabled${NC}"
else
    echo -e "${YELLOW}  ⚠ .mcp.json already exists (skipping)${NC}"
fi
echo -e "${CYAN}  Tip: For Copilot CLI MCP tools, run scripts/setup-copilot-mcp.sh after install.${NC}"

# -------------------------------------------
# Step 5: Create vault folders
# -------------------------------------------
echo ""
echo -e "${BOLD}[5/6] Creating vault structure...${NC}"

FOLDERS=(
    "00-Inbox/Meetings"
    "00-Inbox/Ideas"
    "00-Inbox/Slack"
    "01-Quarter_Goals"
    "02-Week_Priorities"
    "03-Tasks"
    "04-Projects"
    "05-Areas/People/Internal"
    "05-Areas/People/External"
    "05-Areas/Companies"
    "05-Areas/Career/Evidence/Achievements"
    "05-Areas/Career/Evidence/Feedback_Received"
    "05-Areas/Career/Evidence/Skills_Development"
    "06-Resources/Amp_System"
    "06-Resources/Templates"
    "07-Archives"
    "System/Memory"
    "System/Session_Learnings"
    "System/Skill_Ratings"
)

CREATED=0
for folder in "${FOLDERS[@]}"; do
    if [ ! -d "$folder" ]; then
        mkdir -p "$folder"
        CREATED=$((CREATED + 1))
    fi
done

# Copy initial files from templates
if [ ! -f "03-Tasks/Tasks.md" ]; then
    cp System/Templates/Tasks.md 03-Tasks/Tasks.md
fi
if [ ! -f "System/usage_log.md" ]; then
    cp System/Templates/usage_log.md System/usage_log.md
fi

echo -e "${GREEN}  ✓ ${CREATED} folders created${NC}"

# -------------------------------------------
# Step 6: Generate CLAUDE.md from template
# -------------------------------------------
echo ""
echo -e "${BOLD}[6/6] Preparing system instructions...${NC}"
if [ ! -f "CLAUDE.md" ]; then
    cp CLAUDE.md.template CLAUDE.md
    echo -e "${GREEN}  ✓ CLAUDE.md created (will be personalized during onboarding)${NC}"
else
    echo -e "${YELLOW}  ⚠ CLAUDE.md already exists (skipping)${NC}"
fi

# -------------------------------------------
# Done!
# -------------------------------------------
echo ""
echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}${BOLD}  ⚡ Amp is installed!${NC}"
echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${BOLD}Next steps:${NC}"
echo ""
echo -e "  1. If you just installed Homebrew or Copilot CLI,"
echo -e "     quit Terminal and open it again first."
echo ""
echo -e "  2. Change into your Amp directory:"
echo -e "     ${CYAN}cd ${VAULT_PATH}${NC}"
echo ""
echo -e "  3. Launch your AI agent from this directory:"
echo -e "     ${CYAN}copilot${NC}  (GitHub Copilot CLI)"
echo -e "     ${CYAN}claude${NC}   (Claude Code)"
echo ""
echo -e "  4. If Copilot asks you to authenticate,"
echo -e "     type ${CYAN}/login${NC} and finish the browser sign-in."
echo ""
echo -e "  5. Then run ${CYAN}/allow-all${NC} and ${CYAN}/setup${NC}."
echo -e "     It sets up your profile, email routing, and workspace,"
echo -e "     then walks you through opening the vault in Obsidian."
echo ""
echo -e "  6. If ${CYAN}/setup${NC} does not work, restart Terminal,"
echo -e "     ${CYAN}cd${NC} back here, run ${CYAN}copilot${NC} again, and retry."
echo ""
echo -e "  7. After onboarding, try these commands:"
echo -e "     ${CYAN}/daily-plan${NC}    - Plan your day"
echo -e "     ${CYAN}/meeting-prep${NC}  - Prep for a meeting"
echo -e "     ${CYAN}/review${NC}        - End-of-day review"
echo ""
echo -e "  ${BOLD}Vault path:${NC} ${VAULT_PATH}"
echo ""
