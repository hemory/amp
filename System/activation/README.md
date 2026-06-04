# `System/activation/` — Activation Engine data

This directory is the telemetry spine and control surface for Amp's B-1
Activation Engine. Everything here is plain JSONL or YAML so future maintainers
can read and edit it by hand. There is no hidden state.

## Files

| File | Purpose |
|---|---|
| `signals.jsonl` | Raw signals from vault + calendar (Stage 1). Append-only, rotated weekly. |
| `candidates.jsonl` | Extracted "possible offer" rows (Stage 2). Append-only, rotated weekly. |
| `offers.jsonl` | Every offer Amp produced + the user's response (Stage 5). **Permanent.** This is the telemetry spine. |
| `tombstones.jsonl` | "Never suggest this again" markers. Human-editable. |
| `weights.yaml` | Ranker weights. Edit to tune offer selection. |
| `kill.yaml` | **Hard kill switch.** `disabled: true` = engine off, revert to v1 /daily-plan. |
| `quiet-mode.yaml` | Pause the engine until a given date (e.g., vacation). |
| `ghost-log.md` | Human-readable digest of offers Amp *would* have made during ghost mode. |
| `drafts/` | Full text of each drafted offer (referenced by `offer.draft_artifact_path`). |

## Reading `offers.jsonl` by hand

Each line is a JSON object. To see the last 10 offers, pretty-printed:

```bash
tail -n 10 System/activation/offers.jsonl | jq .
```

Key fields: `offer_id`, `type`, `shown`, `hold_reason`, `summary`,
`cited_signals`, `score`, `user_response`. A `shown: false` row with
`hold_reason: "ghost"` is a ghost-mode offer (Sprint 6+).

Note on empty files: `tombstones.jsonl`, `signals.jsonl`, `candidates.jsonl`
and `offers.jsonl` may be zero-byte files. That is valid — the JSONL
specification treats zero rows as the empty list. The pipeline creates
these on first write.

## Using `kill.yaml`

Flip `disabled: true` and the engine short-circuits on the next /daily-plan
run. No restart required.

```yaml
disabled: true
reason: "Amp was making bad offers this week, debugging"
```

The `reason` field is optional and printed on exit.

## Using `quiet-mode.yaml`

Set an `until:` date to pause the engine through that day (inclusive).

```yaml
until: 2026-05-02
reason: "out of office"
```

If `until:` is missing or unparseable, quiet-mode is considered off
(fail-open — the quiet-mode file itself should never crash /daily-plan).

## Graceful degradation

If Amp vanishes tomorrow, nothing here is required to make the vault work.
`offers.jsonl` becomes a readable log of decisions the user made; `ghost-log.md`
is a diary of the ones that were considered. That's by design — see PRD §5.10.
