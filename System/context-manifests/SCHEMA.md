# Context Manifest Schema

Context manifests define what each core workflow should check before it starts gathering content. They keep workflow context explicit, avoid broad vault scans, and make disabled, stale, or unhealthy sources visible.

## File layout

Each workflow has a YAML file at `System/context-manifests/<workflow>.yaml`.

## Fields

| Field | Required | Notes |
| --- | --- | --- |
| `manifest_version` | Yes | Current value: `1` |
| `workflow` | Yes | Matches the skill or workflow name |
| `display_name` | Yes | Human-readable name for reports |
| `workflow_hook` | No | Key under `System/integrations/config.yaml > hooks` used for workflow integration toggles |
| `required_sources` | No | Sources that should exist for high-confidence output |
| `optional_sources` | No | Sources that improve output but should not block it |
| `health_sources` | No | Health signals to surface before output generation |
| `report` | No | Reporting preferences for workflow output |

## Source fields

| Field | Required | Notes |
| --- | --- | --- |
| `id` | Yes | Stable identifier referenced by skill instructions and tests |
| `name` | Yes | Human-readable source name |
| `kind` | Yes | One of `file`, `directory`, `integration`, `command`, `session_learning_health` |
| `path` | For file, directory, health | Repo-relative path |
| `integration` | For integration | Integration key from config, such as `slack` or `google-workspace` |
| `hook_key` | No | Explicit workflow hook flag, such as `use_slack`; defaults to `use_<integration>` |
| `command` | For command | Binary name checked with `command -v` |
| `freshness_days` | File and directory only | Marks source `stale` when latest mtime is older than this many days |
| `recursive` | Directory only | If true, freshness uses the latest file under the directory tree |
| `optional` | No | Optional sources become `skipped` instead of `missing` when absent |
| `legacy_scan` | Health only | Scan session learning markdown for legacy no-summary placeholders |
| `window_days` | Health only | Recent warning window; defaults to 7 |

## Resolution rules

- `file`: available when the path exists. If `freshness_days` is set and the file is older, status is `stale`.
- `directory`: available when the path exists and contains at least one file. Freshness is the latest file mtime, recursively only when `recursive: true`.
- `integration`: available only when both `<integration>.enabled` and the workflow hook flag are enabled in `System/integrations/config.yaml`.
- `command`: available when `command -v <command>` succeeds.
- `session_learning_health`: groups recent `_health.log` warnings and can scan for legacy placeholder summaries.

Workflow skills should run the context-health check before context gathering when available and include a context report when anything is disabled, missing, stale, skipped, or warning.
