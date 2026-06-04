# Amp Analytics Beta

Welcome to the Amp Analytics beta! By activating this feature, you're helping Dave understand how people use Amp so he can make it better.

## What Gets Tracked

**What we track:**
- Which Amp built-in features you use (e.g., "ran /daily-plan", "created a task")
- When features are used (for journey analysis)
- Basic metadata: days since setup, feature adoption score, journey stage

**What we NEVER track:**
- Your content (notes, tasks, meeting content)
- Names of people or companies
- What you actually DO with features
- Any custom skills or MCPs you create
- Your conversations with Claude

## Privacy Commitment

- **Opt-in only:** You choose whether to share analytics
- **One-time ask:** After you decide, you're never asked again
- **Your control:** You can change your decision anytime in `System/user-profile.yaml`
- **Transparent:** See exactly what's tracked in `System/usage_log.md`

## How It Works

1. **Consent prompt:** During your next planning session (`/daily-plan`, `/review`, etc.), you'll be asked once if you want to help improve Amp
2. **Your choice:** Say yes to help, or no thanks — Amp works exactly the same either way
3. **Event firing:** If you opt in, anonymous feature usage events are sent through your configured analytics transport

## Configuration

User consent settings are stored in `System/user-profile.yaml`:

```yaml
analytics:
  enabled: true  # or false if you declined
```

Transport settings are configured via environment variables:

```bash
# Recommended: proxy mode (server-side relay holds Pendo key)
AMP_ANALYTICS_MODE=proxy
AMP_ANALYTICS_ENDPOINT=https://analytics.your-domain/track
AMP_ANALYTICS_PROXY_TOKEN=optional-token

# Direct mode (not recommended for OSS clients)
AMP_ANALYTICS_MODE=direct
PENDO_TRACK_SECRET=your-pendo-track-key
```

Security note:
- Amp no longer bundles a default `PENDO_TRACK_SECRET` in source.
- For public/open-source clients, use proxy mode so write keys stay server-side.

Your consent status is tracked in `System/usage_log.md`:
- `Consent asked: true/false`
- `Consent decision: pending/opted-in/opted-out`
- `Consent date: YYYY-MM-DD`

## Changing Your Mind

To opt out after opting in:
1. Open `System/user-profile.yaml`
2. Set `analytics.enabled: false`
3. Events will stop immediately

To opt in after opting out:
1. Open `System/user-profile.yaml`  
2. Set `analytics.enabled: true`

## Questions?

This is a beta feature. If you have questions or concerns, reach out to Dave directly.

---

*Beta version 0.1.0 • Last updated: 2026-02-04*
