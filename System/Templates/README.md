# Templates

Templates used by Amp automation for consistent structure.

## Available Templates

These templates are actively used by Amp skills:

- **`Person_Page.md`** — Person page structure (used when creating person pages)
- **`Company.md`** — Company page structure (used by `/process-meetings`)
- **`Career_Evidence_Achievement.md`** — Achievement capture (used by `/week-review`, `/resume-builder`)
- **`Career_Evidence_Feedback.md`** — Feedback tracking (used by career system)

## Usage

Amp automatically uses these templates when creating new files through skills and automation. You can modify them to match your preferences.

## Identity Templates

Optional identity and voice templates live under `System/identity/` rather than this folder because they are read as stable agent context, not copied into daily work products.

- `System/identity/amp/SOUL.md.template`
- `System/identity/amp/STYLE.md.template`
- `System/identity/user/README.md`

## Note on Manual File Creation

If you're creating files manually (person pages, company pages, etc.), you can copy these templates as a starting point, but Amp will work fine with any structure you prefer.
