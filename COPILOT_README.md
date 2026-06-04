# Amp + Copilot CLI — Quick Start Guide

This is a **Copilot CLI adaptation** of [Amp](https://github.com/davekilleen/amp) — your AI Chief of Staff. Your work, amplified. Work management, meeting intelligence, relationship tracking, and daily planning.

> **Original project:** https://github.com/davekilleen/amp
> **Adaptation:** Swaps Claude Code / Cursor for GitHub Copilot CLI

---

## What You'll Need

| Requirement | Details |
|---|---|
| **[Copilot CLI](https://gh.io/copilot-install)** | `curl -fsSL https://gh.io/copilot-install \| bash` or `brew install copilot-cli` |
| **Active Copilot subscription** | Often included via GitHub org/enterprise |
| **[Git](https://git-scm.com)** | Any recent version |
| **[Node.js 18+](https://nodejs.org/)** | LTS version |
| **[Python 3.10+](https://www.python.org/downloads/)** | Required for MCP servers (task sync) |

---

## Setup (10 minutes)

### Step 1: Clone the repo

```bash
git clone https://github.com/davekilleen/amp.git ~/Documents/amp
cd ~/Documents/amp
```

### Step 2: Run the Copilot CLI installer

```bash
bash copilot-install.sh
```

This installs dependencies, configures MCP servers, and sets up Copilot CLI hooks.

If `copilot-install.sh` doesn't exist yet (you're using a vanilla Amp clone), run the original installer first, then the hooks setup:

```bash
bash install.sh
bash setup-copilot-hooks.sh
```

### Step 3: Launch Copilot CLI and configure

```bash
copilot
```

Then inside Copilot CLI:

```
/allow-all          ← Grant vault access
/mcp                ← Verify MCP servers are running
/setup              ← Configure your role (takes ~5 min)
```

**That's it.** All 25+ Amp skills now work through Copilot CLI.

---

## What Changed from Original Amp

| Component | Original (Claude Code) | This Adaptation (Copilot CLI) |
|---|---|---|
| **Client** | Cursor / Claude Code | GitHub Copilot CLI (`copilot`) |
| **Instructions** | `CLAUDE.md` | `CLAUDE.md` + `AGENTS.md` (both read by Copilot CLI) |
| **Hooks config** | `.claude/settings.json` | `.github/hooks/hooks.json` |
| **Hook scripts** | `.claude/hooks/*.sh/.cjs` | Same scripts + adapter wrappers in `.github/hooks/` |
| **MCP servers** | Auto-detected from `.mcp.json` | Same — also visible via `/mcp` command |
| **Skills** | `.claude/skills/` | Same — Copilot CLI reads `.claude/skills/` natively |
| **Auth** | `claude auth` (Anthropic) | Auto via GitHub login |
| **Model** | Claude only | `/model` to switch (Claude, GPT-5, etc.) |
| **Cost** | $20/mo Claude Pro | Copilot subscription (often free via org) |

### What You Gain

- **Native GitHub integration** — issues, PRs, repos, code search built-in
- **Multi-model flexibility** — Claude Sonnet 4.5, GPT-5, etc. via `/model`
- **`/research`** — Deep web investigation with citations
- **`/review`** — Code review agent
- **Lower cost** — Often included in existing GitHub plans

### What's Different

- **No global hooks** — Copilot CLI hooks are per-repo only (Claude Code supports global)
- **No Cursor IDE integration** — Terminal only (but that's the point!)
- **Skills reference "Claude"** — The AGENTS.md tells the AI to interpret these as self-references

---

## Files Added/Modified

### New Files
| File | Purpose |
|---|---|
| `AGENTS.md` | Copilot CLI instruction file (agent-aware Amp context) |
| `.copilot-instructions.md` | Copilot CLI tips and quick reference |
| `copilot-install.sh` | One-command installer for Copilot CLI |
| `setup-copilot-hooks.sh` | Creates `.github/hooks/` and copies adapter scripts |
| `.claude/hooks-copilot.json` | Hooks config (copied to `.github/hooks/hooks.json`) |
| `.claude/hooks/copilot-session-start.sh` | Adapter: translates Copilot JSON → sets `$CLAUDE_PROJECT_DIR` |
| `.claude/hooks/copilot-session-end.sh` | Adapter: session end with env var bridge |
| `.claude/hooks/copilot-safety-guard.sh` | Adapter: translates block format (exit 2 → JSON deny) |
| `.claude/hooks/copilot-context-injector.cjs` | Adapter: person/company context with `toolArgs` parsing |

### Patched Files (backwards-compatible)
| File | Change |
|---|---|
| `.claude/hooks/session-start.sh` | Added `$CLAUDE_PROJECT_DIR` fallback for Copilot CLI |
| `.claude/hooks/session-end.sh` | Added `$CLAUDE_PROJECT_DIR` fallback for Copilot CLI |
| `.claude/hooks/person-context-injector.cjs` | Added `toolArgs` (JSON string) parsing |
| `.claude/hooks/company-context-injector.cjs` | Added `toolArgs` (JSON string) parsing |

All patches are additive — the original Claude Code behavior is preserved.

---

## Daily Usage

Same commands as the original Amp:

| Command | What It Does |
|---|---|
| `/daily-plan` | Start your day with 2-3 priorities |
| `/meeting-prep` | Prep for upcoming meetings |
| `/daily-review` | End-of-day reflection and learning capture |
| `/triage` | Process inbox, meetings, and commitments |
| `/career-coach` | Weekly reports, self-reviews, promotion prep |
| `/amp-level-up` | Discover features you haven't tried |
| `/amp-demo on` | Explore with sample data |

---

## Troubleshooting

**Skills not loading?** Make sure you're running `copilot` from the Amp repo root directory.

**MCP servers not working?** Run `/mcp` to check status. If errors, try:
```bash
python3 -m pip install --upgrade pip
pip3 install --user "mcp>=1.0.0,<2.0.0" pyyaml python-dateutil
```

**Hooks not firing?** Run `bash setup-copilot-hooks.sh` to ensure `.github/hooks/` exists and has the config.

**Permission errors?** Run `/allow-all` inside Copilot CLI to grant full vault access.

---

## Credits

- **[Amp](https://github.com/davekilleen/amp)** by [Dave Killeen](https://www.linkedin.com/in/davekilleen/)
- Adapted for Copilot CLI by this automation
