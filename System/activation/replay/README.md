# Activation Replay Harness (Sprint 5)

Offline calibration instrument for the B-1 Activation Engine. Runs the full
pipeline — extract → rank → draft → score — against pre-recorded fixtures,
deterministically, with no network and no LLM. This is how the user grades
offers in the §9.1 "offline replay" phase, and how Amp self-applies the
rubric later (per §10 locked decision #4).

## Layout

```
System/activation/replay/
├── README.md                 ← this file
├── fixtures/
│   ├── .gitkeep
│   └── sample-01/            ← canonical reference fixture
│       ├── meta.yaml
│       ├── signals.jsonl
│       ├── extract_response.json
│       ├── draft_responses/
│       │   └── {offer_id}.json
│       ├── offers.jsonl      (optional — prior offers)
│       ├── tombstones.jsonl  (optional — prior tombstones)
│       └── grades.jsonl      (optional — human grades)
└── runs/                     ← created on --write-run; scoped per fixture
    └── <fixture_id>/<timestamp>/
```

Every fixture is a self-contained directory. Run outputs are *always* written
under `runs/<fixture_id>/<timestamp>/` — the live `System/activation/*.jsonl`
files are never touched by replay.

## Fixture schema

### `meta.yaml` (required)

| Field | Type | Notes |
|---|---|---|
| `id` | str | Fixture id. Becomes part of replay `offer_id`s. |
| `description` | str | Free-form. |
| `created_at` | ISO timestamp | When the fixture was authored. |
| `now` | ISO timestamp | **Frozen clock.** All time-dependent logic (recency, novelty, ghost-mode gating) uses this. |
| `days_since_install` | int | Passed to `rank`. <7 forces ghost. |
| `acceptance_rate` | float or null | Trailing acceptance rate, if known. |
| `ghost` | bool | Optional; forces ghost mode regardless of install age. |

### `signals.jsonl` (required)

One `Signal` row per line. Must satisfy `core.activation.schemas.Signal`.

### `extract_response.json` (required)

A JSON array of candidate dicts — the exact output you would have captured
from the LLM during `extract-apply`. Candidates citing signal_ids outside
this fixture's `signals.jsonl` are rejected by `apply_extract_response`
(same hallucination gate as §4.2 of the design doc). **`sample-01` includes
one deliberate bad-citation row (`c_sample01_BAD` cites
`sig_hallucinated_summit`) so every replay exercises the gate.**

### `draft_responses/{offer_id}.json` (optional)

One LLM draft response per offer, keyed on the replay `offer_id`. Replay
offer ids follow the pattern `o-replay-<fixture_id>-<NNN>` (zero-padded 3
digits), sorted by rank score descending. If no response is recorded for an
offer, the offer is produced without a draft and the rubric's
`length_discipline` dimension short-circuits to 1.0 for it.

### `grades.jsonl` (optional)

One `Grade` row per offer: `{offer_id, human_score (0..1), reason,
graded_at, grader}`. When present, `replay` prints the Pearson correlation
between rubric `overall` and `human_score` (how the rubric proves
calibration).

## CLI

All commands run from repo root with the repo's venv.

```bash
# Run a fixture end-to-end and print scores.
.venv/bin/python -m core.activation replay --fixture System/activation/replay/fixtures/sample-01

# Same, but persist run outputs under replay/runs/sample-01/<stamp>/.
.venv/bin/python -m core.activation replay --fixture ... --write-run

# Machine-readable output for downstream tools.
.venv/bin/python -m core.activation replay --fixture ... --json

# Append a human grade to a fixture.
.venv/bin/python -m core.activation grade --fixture ... \
    --offer-id o-replay-sample-01-000 --score 0.85 \
    --reason "specific, time-bounded" --grader user

# Run the rubric against a live offer (read-only — no state mutation).
.venv/bin/python -m core.activation rubric-check --offer-id o-...
```

The kill-switch and quiet-mode files still apply — Amp refuses to replay if
the engine is killed or in quiet mode, the same as any other subcommand.

## Rubric (summary)

Six dimensions, all 0..1, equal-weighted `overall`. Full spec in
`core/activation/rubric.py`.

| Dimension | What it measures |
|---|---|
| `grounding` | Fraction of meaningful tokens in summary+draft that appear in some cited signal excerpt (case-insensitive, light stem). |
| `specificity` | Contains an `ACTION_VERBS` entry **and** a proper-noun-like token or a date-shaped token. Binary-ish: 1.0 / 0.5 / 0.0. |
| `staleness` | `max(0, 1 − staleness_days / 14)`. Zero at ≥14 days. |
| `novelty` | 0 if a prior offer within 7 days shares ≥50% of cited signals and same `type`; else 1. |
| `length_discipline` | 1 if draft is within the per-type cap (`draft.LENGTH_CAPS_WORDS`); else `1 − overage_ratio`, clamped. |
| `citation_discipline` | 1 if citations are non-empty AND every cited signal resolves to the provided universe; else 0. |

## Workflow: add a new fixture

1. `mkdir fixtures/<new-id>` and author a `meta.yaml`.
2. Populate `signals.jsonl` with hand-picked or captured signals.
3. Run the extract handshake you would normally run, capture the raw LLM
   output, and save it as `extract_response.json`. (To keep the fixture
   LLM-free after that, **never** include real user prompts or identity
   bundle fragments — just the model's candidate array.)
4. Run `replay --fixture fixtures/<new-id>` to see which offers materialize
   and what offer_ids the ranker mints.
5. For each offer you want to exercise the drafting stage on, capture a
   draft LLM response and save it as
   `draft_responses/<offer_id>.json`.
6. (Optional) Grade via `activation grade ...` to populate `grades.jsonl`.
7. Add a test that asserts the fixture's invariants (see
   `tests/activation/test_replay_run.py` for the pattern).

## Why this exists

Per design doc §13 success criteria #1: **B-1 does not ship until offline
replay mean grade ≥2.0 across ≥30 offers.** This harness is the only
instrument that can produce that measurement without risking the real
vault or waiting on a real ritual.
