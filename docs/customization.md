# Customizing Amp

Amp is designed to adapt to how you work. Here's how to make it yours.

## Strategic Pillars

Amp now keeps onboarding lighter by creating a temporary `General` pillar during setup. When you're ready, replace it with your 2-4 real strategic focus areas in `System/pillars.yaml`.

**To change pillars:**

Edit `System/pillars.yaml`:
```yaml
pillars:
  - id: "product_strategy"
    name: "Product Strategy"
    description: "Long-term product direction and roadmap"
    keywords:
      - product
      - strategy
      - roadmap
      - vision

  - id: "team_growth"
    name: "Team Growth"
    description: "Hiring, mentoring, and team development"
    keywords:
      - team
      - hiring
      - mentoring
      - growth
```

Keywords help Amp auto-suggest the right pillar when you create tasks.

## Communication Style

Control how Amp talks to you in `System/user-profile.yaml`:

```yaml
communication:
  formality: "professional_casual"  # formal, professional_casual, casual
  directness: "balanced"            # very_direct, balanced, supportive
  detail_level: "concise"           # concise, balanced, comprehensive
  career_level: "senior"            # junior, mid, senior, leadership
  coaching_style: "collaborative"   # encouraging, collaborative, challenging
```

Onboarding sets the basic `formality` and `directness` defaults. You can adjust `detail_level`, `career_level`, and `coaching_style` here later if you want Amp to coach differently.

## User Extensions (Persistent Preferences)

The `USER_EXTENSIONS` block in `CLAUDE.md` is your space for custom instructions. Anything you put here persists across updates.

```markdown
## USER_EXTENSIONS_START

### My Preferences
- Always open new files in Obsidian
- No em dashes in any output
- When creating tasks, default to P2 unless I say otherwise

### My Frameworks
When I ask about strategy, use the MECE framework.

## USER_EXTENSIONS_END
```

To add a preference, just tell Amp: "Remember that I prefer bullet points over paragraphs." It will write it to the extensions block.

## Identity and Voice Templates

For stable guidance that should survive across sessions, use the optional templates in `System/identity/`:

- `System/identity/amp/SOUL.md.template` for Amp's operating principles
- `System/identity/amp/STYLE.md.template` for Amp's voice and formatting rules
- `System/identity/user/README.md` for guidance on user-declared identity and writing style files

Copy a template to the matching active filename, for example `SOUL.md.template` to `SOUL.md`, then customize it. Only add facts the user explicitly provides. Do not store runtime logs, tasks, meeting notes, secrets, or inferred sensitive attributes in identity files. Updates may refresh templates, but active identity files are user-owned. See the [0.2.0 update guide](update-guide-0.2.0.md#identity-templates-after-update) before copying template changes into an existing setup.

## Custom Skills

Create a skill that Amp can invoke with a `/command`:

```
/create-skill
```

This generates a protected skill file (suffixed `-custom`) that will never be overwritten by updates.

Skills are markdown files that define:
1. When to trigger
2. What context to gather
3. How to generate output
4. Example scenarios

## Custom MCP Servers

Build a tool integration for any service:

```
/create-mcp
```

Or install from the marketplace:

```
/integrate-mcp
```

## Role Templates

Amp adapts to your role through pillars and communication style. Some role-specific patterns:

**Engineering Manager:** Sprint tracking, 1:1 templates, tech debt monitoring
**Product Manager:** PRD templates, roadmap tracking, stakeholder mapping
**Program Manager:** Cross-functional tracking, status reports, RACI templates
**Sales:** Pipeline tracking, account management, call prep
**L&D / Enablement:** Program lifecycle, evaluation frameworks, facilitator tools

These aren't separate "modes." They emerge from how you configure your pillars, create skills, and build your vault over time.

## Priority Limits

Default limits are enforced by the Work MCP:
- P0 (urgent): max 3
- P1 (important): max 5
- P2 (normal): max 10
- P3 (backlog): unlimited

Change these in `System/pillars.yaml`:
```yaml
priority_limits:
  P0: 3
  P1: 5
  P2: 10
```
