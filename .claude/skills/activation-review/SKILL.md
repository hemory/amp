---
name: activation-review
description: Review proposed actions surfaced by the B-1 Activation Engine. Gathers recent signals, extracts candidates, ranks them, drafts artifacts, and captures the user's response per offer. Standalone — does not modify /daily-plan.
context: fork
---

## Purpose

The Activation Engine (B-1) turns Amp's passive vault context into a small, ranked list of prepared actions. This skill is the human-in-the-loop ritual for reviewing those actions. `/daily-plan` is intentionally untouched so the activation engine can be exercised independently before it is welded into the morning ritual.

The skill is a thin wrapper over the `python -m core.activation` CLI. All LLM calls are handshake-mediated: the CLI emits a JSON prompt, the agent runs the model, the CLI validates + writes the result. No shortcuts — the citation-required gate (§6.1 of the design doc) and the length-cap hallucination guard are enforced by `draft-apply`.

---

## Frontmatter / config

CLI surface used by this skill:

| Stage | Command |
|---|---|
| 1 — gather | `python -m core.activation gather` |
| 2a — extract prompt | `python -m core.activation extract-prompt` |
| 2b — extract apply | `python -m core.activation extract-apply --input FILE --batch-id ID` |
| 3 — rank | `python -m core.activation rank --days-since-install N [--acceptance-rate R] [--ghost]` |
| 4a — draft prompt | `python -m core.activation draft-prompt --offer-id ID` (or `--all`) |
| 4b — draft apply | `python -m core.activation draft-apply --offer-id ID --input FILE` |
| 5 — acceptance rate | `python -m core.activation acceptance-rate [--window-days 14]` |
| 6 — log response | `python -m core.activation log --offer-id ID --response {accepted\|accepted_with_edits\|rejected\|never_again\|snoozed\|ignored\|viewed} [--reason TEXT] [--ghost]` |
| 7 — ghost status | `python -m core.activation ghost-status [--json]` |
| 7 — ghost review | `python -m core.activation ghost-review [--window-days N] [--mark-complete] [--notes TEXT]` |
| 7 — ghost exit | `python -m core.activation ghost-exit --acknowledge` |

Run all commands from the repo root with the repo's venv: `.venv/bin/python -m core.activation ...`.

---

## Safety notes

- **Kill switch:** `System/activation/kill.yaml` with `disabled: true` halts everything. Check it before starting.
- **Quiet mode:** `System/activation/quiet-mode.yaml` with an `until:` date suspends activation until the date passes.
- **Ghost mode:** Enter ghost mode if the install is <7 days old (pass `--days-since-install N`) OR if `--ghost` is supplied to `rank`. In ghost mode, offers are logged but clearly labeled as non-actionable; `log` entries are tagged `ghost`.
- **Citation gate:** `draft-apply` rejects any draft citing a signal that wasn't attached to the offer. Do not try to work around a rejection — re-run the LLM with the original handshake.
- **Never auto-send.** Every offer produces a draft. the user presses send. Always.

---

## Process

### Step 0: Safety preflight

1. Read `System/activation/kill.yaml`. If `disabled: true` → stop, tell the user activation is off, exit.
2. Read `System/activation/quiet-mode.yaml`. If `until` is in the future → stop, tell the user quiet mode is active until that date, exit.
3. Determine `days_since_install`:
   - Use the mtime of `System/activation/README.md` or the first line of `System/activation/ghost-log.md` as the install anchor.
   - If <7, you will be in ghost mode for Step 3.

### Step 1: Gather fresh signals

```bash
.venv/bin/python -m core.activation gather
```

Read the summary line (total signals, by source). If 0 signals, stop with a short message: "No fresh signals — nothing to review."

### Step 2: Extract candidates

1. Emit the handshake: `.venv/bin/python -m core.activation extract-prompt` → capture stdout, note the `batch_id`.
2. Call the LLM with `system_prompt` + `user_prompt` from the handshake. The LLM must return a JSON array of Candidate objects matching the provided `schema`.
3. Save the response to a temp file inside the repo workspace (do NOT use `/tmp`), e.g. `System/activation/.last-extract-response.json`.
4. Apply: `.venv/bin/python -m core.activation extract-apply --batch-id <id> --input <path>`
5. Note the `accepted=N rejected=M` line. If >0 rejected, surface the first reject reason to the user so he can see how the gate is working.
6. Repeat for additional batches only if `extract-prompt --batch-index N` returns more batches; Sprint 4 ships batch 0 by default.

### Step 3: Rank

First compute the acceptance rate for the throttle:

```bash
RATE=$(.venv/bin/python -m core.activation acceptance-rate)
```

- If `RATE == "insufficient_data"` OR `days_since_install < 7` → use `--days-since-install $N` (ghost mode will engage automatically for new installs).
- Otherwise → pass both `--days-since-install $N --acceptance-rate $RATE`.

```bash
.venv/bin/python -m core.activation rank --days-since-install $N --acceptance-rate $RATE
```

Output line is `surfaced=X ghost=Y dropped=Z`. Remember: in ghost mode `surfaced=0` is correct.

### Step 4: Draft per offer

For each offer in `System/activation/offers.jsonl` where `shown: true` (or all ghost offers if ghost mode — see Step 6):

1. `.venv/bin/python -m core.activation draft-prompt --offer-id <id>` → capture stdout.
2. Call the LLM with the handshake. Respect the `length_cap_words` in the handshake.
3. Save response to `System/activation/.last-draft-response.json` (rewrite for each offer).
4. `.venv/bin/python -m core.activation draft-apply --offer-id <id> --input <path>`
5. If `rejected=1`, read the reason on stderr. Most common causes: hallucinated citation, over-length, missing field. Re-run the LLM with the same handshake and tighter guidance. Do not mutate the handshake itself.

### Step 5: Present offers to the user

Render a clean numbered summary:

```
Activation review — {{date}}   ({{mode: live | ghost (day N of 7)}})

1. [meeting_followup] Send workshop followup to D.Lin
   Why: Monday's 1:1 — committed to send recap by Friday.
   Draft: System/activation/drafts/{{offer_id}}.md

2. [commitment_reminder] Q2 narrative due tomorrow
   ...
```

Rules:
- Show at most what `rank` surfaced. Do not expose budget-held offers.
- Ghost mode: show the same list but with a clear banner up top: "👻 Ghost mode — Amp is learning your patterns. Nothing will be acted on. Mark each offer anyway; your judgments feed the self-throttle."

### Step 6: Capture response per offer

For each numbered offer, ask the user: accept / edit / reject (with reason?) / snooze / ignore.

For each answer run:

```bash
.venv/bin/python -m core.activation log --offer-id <id> --response <response> [--reason "<reason>"] [--ghost]
```

- Pass `--ghost` when you are in ghost mode so the `ghost-log.md` entry is tagged correctly.
- `rejected` records a "not now" Event. The same pattern is hard-suppressed for 14 days (Sprint 7 H1) but no Tombstone is created — the candidate can resurface after the window if the underlying signal is still relevant.
- `never_again` is the permanent stop. It appends a Tombstone (the user won't see that pattern again) **and** records an Event. Use this when the user says "stop suggesting this kind of thing".
- All responses now also append to `System/activation/response-events.jsonl` (Sprint 7 H3, append-only). Throttle, day-7 acceptance, and weekly metrics are computed from this log.

### Sprint 7 audit / housekeeping commands
- `python -m core.activation handshake-gc --older-than-days 7` — sweep stale extract/draft handshake JSONs from `System/activation/handshakes/`.
- `python -m core.activation policy-check [--acknowledge] [--json]` — sha256 hash of weights+grounding+prompts+identity+rubric. If it changed since baseline, `post-review-pause.yaml` is auto-set. `--acknowledge` clears the pause and rebaselines.
- `python -m core.activation weekly-metrics [--week-ending YYYY-MM-DD] [--json]` — emits the §11 review summary (offers proposed/surfaced/held/decided, draft adoption, response latency p50/p95, grounding pass rate, throttle/ghost active days).
- `python -m core.activation ghost-status --check-exit-ready [--json]` — prints the H4 predicate matrix (P1 install window, P2 manual, P3 pause, P4 distinct review days, P5 decided offers, P6 day-7 acceptance) and the overall `ready` flag. Use BEFORE running `ghost-exit --acknowledge`.
- `python -m core.activation ghost-exit --acknowledge` — refuses unless all H4 predicates pass. `--force` bypasses the gate (manual audit required, audit row recorded).
- `snoozed` is a re-rank next run, not a hard re-surface (per design doc §10.3).

### Step 7: Close out

Summarize for the user:

- Total offers surfaced
- Accepted / rejected / snoozed / ignored counts
- New tombstones count (if any)
- Next review suggested date

If ghost mode: remind the user that ghost exits when `days_since_install >= 7` AND ≥5 days of ghost offers exist AND at least one review has happened.

---

## Output

This skill does not produce a markdown file in the vault. Its outputs are:
- Updated `System/activation/offers.jsonl` with user_response per row
- Appended rows in `System/activation/tombstones.jsonl` for rejects
- Appended lines in `System/activation/ghost-log.md` for every response
- Draft artifacts under `System/activation/drafts/{offer_id}.md`

The spine is the log. If Amp vanishes tomorrow, `offers.jsonl` + `drafts/` are still a clean, readable record of decisions the user made.

---

## Graceful Degradation

- **No identity files:** `draft-prompt` emits a warning to stderr; drafting proceeds with generic voice. Drafts may feel flatter until `System/identity/` is populated.
- **No signals:** Step 1 bails early.
- **No candidates after extract:** Step 3 produces no offers; say so and exit.
- **LLM unavailable:** Abort after Step 1 with the user's signals preserved. Activation is a per-ritual concern; there is no "partial run" state to clean up.

---

## Calibration mode (Sprint 5)

The engine ships an **offline replay harness** at `System/activation/replay/`. Replay is how we exercise the full pipeline *without* running against the live vault, the network, or an LLM — responses are pre-recorded in fixtures. This is the instrument that produces the §13 success-criterion #1 measurement ("mean grade ≥2.0 across ≥30 offers") before B-1 is allowed to go live.

Use replay when:
- the user is grading a batch (the first-30-offers pass per §10 locked decision #4).
- You're tuning `weights.yaml` and want to know whether a change helped or hurt.
- You're investigating a production regression — reproduce it with a fixture, then iterate.

CLI surface:

| Stage | Command |
|---|---|
| Run + score a fixture | `.venv/bin/python -m core.activation replay --fixture PATH [--write-run] [--json]` |
| Append a human grade | `.venv/bin/python -m core.activation grade --fixture PATH --offer-id ID --score 0..1 --reason "TEXT" [--grader user]` |
| Score a live offer | `.venv/bin/python -m core.activation rubric-check --offer-id ID [--json]` |

Replay is read-only on `System/activation/*.jsonl` unless `--write-run` is passed, in which case outputs land under `System/activation/replay/runs/<fixture_id>/<timestamp>/` — never in the live activation files. The kill switch and quiet-mode file still apply: replay refuses to run if the engine is disabled or in quiet mode.

**daily-plan guard (unchanged):** This skill still does not modify `/daily-plan`. Calibration mode is a sibling ritual, not a front-end.

---

## Self-grading (Amp applies the rubric)

Per design doc §10 locked decision #4, Amp may apply the rubric *after* the user has graded the first 30 live offers and calibration has been verified. Until then, Amp surfaces offers but does not publish rubric scores as judgments — only the user's grades count for acceptance metrics.

Once calibration is established, Amp's self-grading flow inside the daily review:

1. After the user responds to each live offer, run `rubric-check --offer-id <id> --json`.
2. Report the `overall` score and any dimension below 0.6 to the user as part of the close-out summary. Example: *"Rubric gave this offer 0.72 overall — flagged `grounding=0.55` because the draft referenced a figure not present in the cited signals. Confidence noted."*
3. Do **not** use the rubric to silently suppress offers. The rubric is a reporting instrument for now; throttling decisions still come from acceptance-rate telemetry per §4.3.
4. If Amp's rubric disagrees materially with the user's grade on a fixture (|delta| > 0.3 across ≥3 offers in a fresh replay), stop self-grading and raise the discrepancy to the user. That is a calibration failure, not a style disagreement.

The rubric is defined in `core/activation/rubric.py` and scores six dimensions: grounding, specificity, staleness, novelty, length discipline, citation discipline. Equal weights for v1 — per §9 the weighting is intentionally left unlearned so that calibration exposes which dimensions actually predict the user's judgment.


---

## Ghost-mode flow (Sprint 6)

Ghost mode is the §7 / §10-#2 safeguard: the engine runs the full pipeline but does NOT surface offers. This skill is ghost-aware as of Sprint 6. The **/daily-plan ritual remains untouched** — ghost mode lives entirely inside `/activation-review`.

### Detect ghost state

Before Step 5 (presentation), call:

```bash
.venv/bin/python -m core.activation ghost-status --json
```

Parse the JSON. If `active: true`, the engine is in ghost mode and `reason` will be one of:

- `install_window` — first 7 days since `install.yaml::install_date`. `expected_end` tells you when the window ends.
- `manual` — `System/activation/ghost-mode.yaml` has `active: true`. May have an `until: YYYY-MM-DD`.
- `post_review_pause` — `System/activation/post-review-pause.yaml` exists (Sprint 7 will populate this; Sprint 6 only honors it as a flag).

### When in ghost mode

1. Skip the live presentation (Step 5). Instead run:
   ```bash
   .venv/bin/python -m core.activation ghost-review --window-days 7
   ```
   This emits the digest to stdout and archives a copy under `System/activation/ghost-review-{YYYYMMDD}.md`. Present the digest verbatim to the user.
2. For each held offer in the digest, ask the user: accept / edit / reject (with reason?) / snooze / ignore. **Even though offers are not actioned in ghost, recording responses calibrates the engine.**
3. Run `log` per response. The `log` CLI now infers ghost mode from the offer's `hold_reason`, so you no longer need to pass `--ghost`:
   ```bash
   .venv/bin/python -m core.activation log --offer-id <id> --response <response>
   ```
   The ghost-log entry will be tagged `mode=ghost` automatically.
4. After all decisions are recorded, call:
   ```bash
   .venv/bin/python -m core.activation ghost-review --mark-complete --notes "<short summary>"
   ```
   This appends a structured `ghost-review-complete` marker to `ghost-log.md`. The `ghost-exit` ritual requires ≥1 such marker in the past 7 days.

### Suggesting ghost exit

After ≥3 days of completed ghost reviews (count the marker payloads with `find_recent_ghost_reviews` or eyeball `ghost-log.md`), AND the install window has elapsed (`days_since_install >= 7`), suggest to the user:

```bash
.venv/bin/python -m core.activation ghost-exit --acknowledge
```

`ghost-exit` will refuse if:

- `--acknowledge` is missing (no accidental exits).
- The install window has not elapsed.
- No ghost-review-complete marker exists in the past 7 days.
- `ghost-mode.yaml::active: true` (the user must clear it himself).

On success it writes `ghost_exited_at` to `install.yaml` and the next `rank` run will surface offers normally.

### /daily-plan guard (still unchanged)

This skill still does NOT modify `/daily-plan`. Ghost mode lives entirely inside `/activation-review`; `/daily-plan` is untouched.
