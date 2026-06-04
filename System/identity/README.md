# Identity Templates

Amp can optionally use identity files to keep stable operating principles and voice guidance separate from day-to-day instructions.

These files are templates only. They should contain generic guidance during installation and user-declared information after onboarding. Do not store secrets, access tokens, private meeting notes, or unverified assumptions here.

## Recommended Structure

```text
System/identity/
├── README.md
├── amp/
│   ├── SOUL.md
│   └── STYLE.md
└── user/
    ├── SOUL.md
    └── STYLE.md
```

- `amp/SOUL.md` describes how Amp should operate in this vault: principles, boundaries, quality bar, and refusal patterns.
- `amp/STYLE.md` describes Amp's response style: tone, formatting, verbosity, and writing rules.
- `user/SOUL.md` stores user-declared identity and working context that should not be inferred.
- `user/STYLE.md` stores the user's voice for drafts written on their behalf.

If these files do not exist, Amp falls back to `CLAUDE.md`, `System/user-profile.yaml`, and the `USER_EXTENSIONS` block.

## Privacy Rules

- Only include identity facts the user explicitly provides.
- Do not infer sensitive attributes from names, roles, locations, or collaborator networks.
- Keep examples generic in templates.
- Keep runtime logs, tasks, projects, and meeting notes in their normal vault locations, not in identity files.

## Updates and Existing Users

Updates may add or refresh `.template` files in this directory, but active identity files are user-owned and should not be overwritten automatically. If you already have `SOUL.md` or `STYLE.md` files, compare the new templates manually and copy only the guidance you want.

Existing users can discover these templates through `docs/customization.md` and the 0.2.0 safe update guide. After changing active identity files, restart the agent session so the new guidance is loaded.
