# Integration Configuration

This directory documents optional integration settings. Real credentials, tokens, sync state, workspace IDs, and user-specific configuration must stay local and untracked.

Use the example files as starting points:

- `config.example.yaml` for integration enablement and workflow hooks.
- `slack.example.yaml` for optional Slack intelligence configuration.

Do not commit:

- `config.yaml`
- `slack.yaml`
- `.sync-state.json`
- Any file containing API keys, OAuth tokens, workspace cookies, tenant IDs, or real task/project IDs.

Before using an integration, Amp should check the local config first and fall back to the markdown vault when the integration is disabled or missing.
