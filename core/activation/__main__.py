"""CLI entry point: `python -m core.activation run [--dry-run]`.

Sprint 1 scope:
  - Honor kill switch at the earliest possible point.
  - Honor quiet-mode.
  - --dry-run prints the resolved config summary.
  - Otherwise print a "skeleton, not wired" message and exit 0.
  - NEVER call gather/extract/rank/draft/surface/log in Sprint 1.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import List, Optional

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

from . import __version__, paths
from .config import load_config, load_weights
from .draft import (
    apply_draft_response,
    build_draft_prompt,
    load_identity,
    write_draft_file,
)
from .extract import apply_extract_response, batch_signals, build_extract_prompt, make_batch_id
from .gather import gather
from .ghost import (
    GHOST_REVIEW_LOOKBACK_DAYS,
    GhostState,
    compute_ghost_state,
    find_recent_ghost_reviews,
    mark_ghost_review_complete,
    read_install_date,
    write_install_field,
)
from .io_jsonl import append_jsonl, read_jsonl, rewrite_jsonl
from .kill_switch import kill_status
from .log import compute_acceptance_rate, record_response
from .quiet_mode import quiet_status
from .rank import rank as rank_candidates
from .replay import FixtureError, load_fixture, run_replay
from .rubric import compare_with_grades, score_fixture, score_offer
from .schemas import Candidate, Draft, Grade, Offer, Signal, Tombstone
from .surface import render_ghost_digest, write_ghost_digest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m core.activation",
        description="Amp B-1 Activation Engine CLI (Sprint 1 scaffolding).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run the activation pipeline.")
    run_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved config snapshot and exit without doing anything.",
    )

    gather_p = sub.add_parser(
        "gather",
        help="Stage 1 only: walk the vault + calendar, write signals.jsonl.",
    )
    gather_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Gather signals but do NOT write signals.jsonl; print summary only.",
    )

    ep = sub.add_parser(
        "extract-prompt",
        help="Stage 2a: emit LLM handshake JSON for the next signals batch.",
    )
    ep.add_argument("--batch-size", type=int, default=50)
    ep.add_argument("--signals-path", type=str, default=None)
    ep.add_argument(
        "--batch-index",
        type=int,
        default=0,
        help="Which batch to emit (0-based). Defaults to 0.",
    )

    ea = sub.add_parser(
        "extract-apply",
        help="Stage 2b: validate an LLM response and append to candidates.jsonl.",
    )
    ea.add_argument("--input", required=True, help="Path to the LLM response JSON file.")
    ea.add_argument("--batch-id", required=True)
    ea.add_argument("--signals-path", type=str, default=None)
    ea.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Stamp this run id on accepted candidates (Sprint 7 C3). "
             "Defaults to 'run-<batch_id>'.",
    )
    ea.add_argument(
        "--no-grounding-gate",
        action="store_true",
        help="Skip the online grounding overlap check (Sprint 7 C2). "
             "Use only for replay or when the upstream LLM was already gated.",
    )

    rk = sub.add_parser("rank", help="Stage 3: rank candidates and write offers.jsonl.")
    rk.add_argument("--days-since-install", type=int, required=True)
    rk.add_argument("--acceptance-rate", type=float, default=None)
    rk.add_argument("--ghost", action="store_true", help="Force ghost mode.")
    rk.add_argument("--ritual", type=str, default="daily-plan")
    rk.add_argument("--run-id", type=str, default=None,
                    help="Force a specific run_id to rank (Sprint 7 C3).")
    rk.add_argument("--no-throttle", action="store_true",
                    help="Disable Sprint 7 O1 throttle tier (debug / replay).")
    rk.add_argument("--no-run-filter", action="store_true",
                    help="Rank all candidates regardless of run lineage (legacy).")
    rk.add_argument("--rejection-suppress-days", type=int, default=14,
                    help="Days a recently-rejected pattern blocks new offers (H1).")

    dp = sub.add_parser(
        "draft-prompt",
        help="Stage 4a: emit LLM handshake JSON for one or all un-drafted offers.",
    )
    g = dp.add_mutually_exclusive_group(required=True)
    g.add_argument("--offer-id", type=str, help="Emit a handshake for a single offer.")
    g.add_argument(
        "--all", action="store_true",
        help="Emit a handshake for every offer without a draft (JSONL stream).",
    )

    da = sub.add_parser(
        "draft-apply",
        help="Stage 4b: validate an LLM draft response and write the artifact.",
    )
    da.add_argument("--offer-id", required=True)
    da.add_argument("--input", required=True, help="Path to the LLM response JSON file.")

    lg = sub.add_parser(
        "log",
        help="Stage 6: record the user's response on an offer.",
    )
    lg.add_argument("--offer-id", required=True)
    lg.add_argument(
        "--response",
        required=True,
        choices=[
            "accepted", "accepted_with_edits", "rejected",
            "snoozed", "ignored", "viewed", "never_again",
        ],
    )
    lg.add_argument("--reason", type=str, default=None)
    lg.add_argument(
        "--ghost", action="store_true",
        help="Mark this log entry as ghost mode (cosmetic — does not change offer state).",
    )

    ar = sub.add_parser(
        "acceptance-rate",
        help="Print the trailing acceptance rate (float) or 'insufficient_data'.",
    )
    ar.add_argument("--window-days", type=int, default=14)

    rp = sub.add_parser(
        "replay",
        help="Sprint 5: run a fixture through the pipeline + score via rubric.",
    )
    rp.add_argument("--fixture", required=True, help="Path to fixture directory.")
    rp.add_argument(
        "--write-run",
        action="store_true",
        help="Materialize run outputs under System/activation/replay/runs/.",
    )
    rp.add_argument(
        "--json",
        action="store_true",
        help="Print a structured JSON summary (for downstream tooling).",
    )

    gr = sub.add_parser(
        "grade",
        help="Sprint 5: append a human grade to a fixture's grades.jsonl.",
    )
    gr.add_argument("--fixture", required=True)
    gr.add_argument("--offer-id", required=True)
    gr.add_argument("--score", type=float, required=True, help="0..1")
    gr.add_argument("--reason", type=str, required=True)
    gr.add_argument("--grader", type=str, default="user")

    rc = sub.add_parser(
        "rubric-check",
        help="Sprint 5: run the rubric against a live offer (read-only).",
    )
    rc.add_argument("--offer-id", required=True)
    rc.add_argument(
        "--json",
        action="store_true",
        help="Print a structured JSON score object.",
    )

    # --- Sprint 6: ghost mode lifecycle ---
    gs = sub.add_parser(
        "ghost-status",
        help="Sprint 6: print the current GhostState.",
    )
    gs.add_argument("--json", action="store_true", help="Print as JSON.")
    gs.add_argument(
        "--check-exit-ready",
        action="store_true",
        help="Sprint 7 H4: print the ghost-exit predicate matrix.",
    )

    gv = sub.add_parser(
        "ghost-review",
        help="Sprint 6: render a ghost-review digest of held offers.",
    )
    gv.add_argument("--window-days", type=int, default=GHOST_REVIEW_LOOKBACK_DAYS)
    gv.add_argument(
        "--no-write",
        action="store_true",
        help="Print to stdout but do NOT archive a copy.",
    )
    gv.add_argument(
        "--mark-complete",
        action="store_true",
        help="After rendering, append a ghost-review-complete marker to ghost-log.md.",
    )
    gv.add_argument(
        "--notes", type=str, default=None,
        help="Optional notes string included in the ghost-review marker.",
    )

    gx = sub.add_parser(
        "ghost-exit",
        help="Sprint 6: exit ghost mode (requires --acknowledge).",
    )
    gx.add_argument(
        "--acknowledge", action="store_true",
        help="Required: explicit confirmation that you've reviewed.",
    )
    gx.add_argument(
        "--force",
        action="store_true",
        help="Sprint 7 H4/O2: bypass the multi-predicate readiness gate. "
             "Use only when you've manually audited what's missing.",
    )

    # --- Sprint 7: handshake GC, policy hash, weekly metrics ---
    hg = sub.add_parser(
        "handshake-gc",
        help="Sprint 7 C1: garbage-collect old handshake artifacts.",
    )
    hg.add_argument(
        "--older-than-days", type=int, default=7,
        help="Delete handshake JSONs whose mtime is older than this (default 7).",
    )
    hg.add_argument("--json", action="store_true", help="Print JSON summary.")

    pc = sub.add_parser(
        "policy-check",
        help=(
            "Sprint 7: hash weights/grounding/prompts/identity/rubric and pause "
            "the engine if it changed since baseline."
        ),
    )
    pc.add_argument(
        "--acknowledge", action="store_true",
        help="Re-baseline the policy hash and clear any active pause.",
    )
    pc.add_argument("--json", action="store_true", help="Print JSON summary.")

    wm = sub.add_parser(
        "weekly-metrics",
        help="Sprint 7 O4: emit weekly review metrics.",
    )
    wm.add_argument(
        "--week-ending",
        type=str,
        default=None,
        help="ISO date (YYYY-MM-DD) of the inclusive week-end. Default: today UTC.",
    )
    wm.add_argument("--json", action="store_true", help="Print JSON.")
    return parser


def _print_dry_run_summary() -> None:
    cfg = load_config()
    killed, kill_reason = kill_status()
    quiet, quiet_reason, until = quiet_status()

    summary = {
        "version": __version__,
        "sprint": "2 of 7",
        "vault_root": cfg["vault_root"],
        "activation_dir": cfg["activation_dir"],
        "paths": {
            "signals": str(paths.SIGNALS_PATH),
            "candidates": str(paths.CANDIDATES_PATH),
            "offers": str(paths.OFFERS_PATH),
            "tombstones": str(paths.TOMBSTONES_PATH),
            "weights": str(paths.WEIGHTS_PATH),
            "kill": str(paths.KILL_PATH),
            "quiet": str(paths.QUIET_PATH),
            "ghost_log": str(paths.GHOST_LOG_PATH),
            "drafts": str(paths.DRAFTS_DIR),
            "behavioral_model_stub": str(paths.BEHAVIORAL_MODEL_STUB_PATH),
        },
        "weights": cfg["weights"],
        "kill": {"engaged": killed, "reason": kill_reason},
        "quiet": {
            "engaged": quiet,
            "reason": quiet_reason,
            "until": until.isoformat() if until else None,
        },
    }
    print("Amp Activation Engine — dry-run config snapshot")
    print(json.dumps(summary, indent=2, sort_keys=True))


def _print_gather_summary(signals: list, *, wrote: bool, elapsed: float) -> None:
    by_source: Counter[str] = Counter(s.source for s in signals)
    print("Amp Activation Engine — gather summary")
    print(f"  total_signals: {len(signals)}")
    print(f"  latency_s:     {elapsed:.2f}")
    print(f"  wrote_file:    {wrote}")
    if wrote:
        print(f"  output_path:   {paths.SIGNALS_PATH}")
    print("  by_source:")
    for src in sorted(by_source):
        print(f"    {src}: {by_source[src]}")
    preview = signals[:3]
    if preview:
        print("  first_3:")
        for s in preview:
            excerpt = s.excerpt.replace("\n", " ").strip()
            if len(excerpt) > 140:
                excerpt = excerpt[:137] + "..."
            print(
                f"    - [{s.source}] {s.path} @ {s.timestamp}"
            )
            print(f"      id={s.signal_id} excerpt={excerpt!r}")


def _cmd_gather(dry_run: bool) -> int:
    started = time.monotonic()
    signals = gather()
    elapsed = time.monotonic() - started
    if not dry_run:
        rewrite_jsonl(paths.SIGNALS_PATH, (s.to_dict() for s in signals))
    _print_gather_summary(signals, wrote=not dry_run, elapsed=elapsed)
    return 0


def _cmd_extract_prompt(batch_size: int, signals_path: str | None, batch_index: int) -> int:
    from .handshake import write_handshake, hash_weights, hash_identity
    from .policy import _IDENTITY_PARTS

    sp = Path(signals_path) if signals_path else paths.SIGNALS_PATH
    rows = read_jsonl(sp)
    signals = [Signal.from_dict(r) for r in rows]
    batches = batch_signals(signals, max_size=batch_size)
    today = datetime.now(timezone.utc).date()
    if not batches:
        handshake = build_extract_prompt([], make_batch_id(today, 0))
        print(json.dumps(handshake, indent=2, sort_keys=True))
        return 0
    if batch_index < 0 or batch_index >= len(batches):
        print(
            f"batch-index out of range: {batch_index} (have {len(batches)} batches)",
            file=sys.stderr,
        )
        return 2
    batch_id = make_batch_id(today, batch_index)
    batch = batches[batch_index]
    handshake = build_extract_prompt(batch, batch_id)

    # Sprint 7 C1 — persist handshake snapshot.
    try:
        identity_files = [paths.VAULT_ROOT.joinpath(*rel) for rel in _IDENTITY_PARTS]
        write_handshake(
            paths.HANDSHAKES_DIR,
            stage="extract",
            handshake_id=batch_id,
            prompt_text=handshake.get("system_prompt", "") + "\n" + handshake.get("user_prompt", ""),
            payload={
                "system_prompt": handshake.get("system_prompt", ""),
                "user_prompt": handshake.get("user_prompt", ""),
                "signals_snapshot": [s.to_dict() for s in batch],
                "batch_id": batch_id,
            },
            weights_hash=hash_weights(paths.WEIGHTS_PATH),
            identity_hash=hash_identity(identity_files),
        )
    except Exception as e:
        print(f"WARNING: could not write handshake artifact: {e}", file=sys.stderr)

    print(json.dumps(handshake, indent=2, sort_keys=True))
    return 0


def _cmd_extract_apply(
    input_path: str,
    batch_id: str,
    signals_path: str | None,
    *,
    run_id: str | None = None,
    no_grounding_gate: bool = False,
) -> int:
    """Sprint 7: prefer handshake artifact (C1), stamp run lineage (C3), grounding gate (C2)."""
    from .handshake import read_handshake
    from .schemas import Signal as _Signal

    handshake = read_handshake(paths.HANDSHAKES_DIR, stage="extract", handshake_id=batch_id)
    batch: list[Signal]
    if handshake is not None:
        # Snapshot-safe path: signals_snapshot in handshake pins the world the
        # prompt was built from. (Sprint 7 C1)
        snapshot = handshake.get("payload", {}).get("signals_snapshot", [])
        batch = [_Signal.from_dict(r) for r in snapshot]
    else:
        print(
            f"WARNING: no handshake artifact for extract:{batch_id}; "
            "falling back to live re-derivation from signals.jsonl. "
            "Results may differ from the snapshot the prompt was built against.",
            file=sys.stderr,
        )
        sp = Path(signals_path) if signals_path else paths.SIGNALS_PATH
        all_signals = [Signal.from_dict(r) for r in read_jsonl(sp)]
        try:
            index = int(batch_id.rsplit("-", 1)[-1])
        except ValueError:
            print(f"invalid batch-id: {batch_id}", file=sys.stderr)
            return 2
        batches = batch_signals(all_signals)
        if index < 0 or index >= len(batches):
            batch = []
        else:
            batch = batches[index]

    with open(input_path, "r", encoding="utf-8") as f:
        response = json.load(f)

    accepted, rejected = apply_extract_response(
        response,
        batch,
        batch_id,
        run_id=run_id,
        enable_grounding_gate=not no_grounding_gate,
    )
    for cand in accepted:
        append_jsonl(paths.CANDIDATES_PATH, cand.to_dict())
    print(f"accepted={len(accepted)} rejected={len(rejected)}", file=sys.stderr)
    if rejected:
        for r in rejected:
            print(
                f"  reject reason={r.get('reason')} detail={r.get('detail', '')}",
                file=sys.stderr,
            )
    return 0


def _cmd_rank(
    days_since_install: int,
    acceptance_rate: float | None,
    ghost: bool,
    ritual: str,
    *,
    run_id: Optional[str] = None,
    no_throttle: bool = False,
    no_run_filter: bool = False,
    rejection_suppress_days: int = 14,
) -> int:
    from .metrics import acceptance_rate_from_events

    candidates = [Candidate.from_dict(r) for r in read_jsonl(paths.CANDIDATES_PATH)]
    offers = [Offer.from_dict(r) for r in read_jsonl(paths.OFFERS_PATH)]
    tombs = [Tombstone.from_dict(r) for r in read_jsonl(paths.TOMBSTONES_PATH)]
    weights = load_weights()
    signals = [Signal.from_dict(r) for r in read_jsonl(paths.SIGNALS_PATH)]
    sig_index = {s.signal_id: s.timestamp for s in signals}

    now = datetime.now(timezone.utc)

    # Sprint 7 C3 — restrict to the most-recent run by default. Operators can
    # opt out with --no-run-filter (replay tooling, ad-hoc backfills).
    if not no_run_filter:
        target_run = run_id
        if target_run is None:
            # Pick the run with the newest created_at timestamp; ties broken
            # lexicographically by run_id for stability.
            with_lineage = [c for c in candidates if c.created_at]
            if with_lineage:
                with_lineage.sort(
                    key=lambda c: (c.created_at, c.run_id), reverse=True
                )
                target_run = with_lineage[0].run_id
        if target_run is not None:
            candidates = [c for c in candidates if c.run_id == target_run]

    install_date = read_install_date(paths.INSTALL_PATH)
    state = compute_ghost_state(
        install_date=install_date,
        now=now,
        manual_yaml_path=paths.GHOST_MODE_PATH,
        ghost_review_log_path=paths.GHOST_LOG_PATH,
        post_review_pause_path=paths.POST_REVIEW_PAUSE_PATH,
    )
    if ghost and not state.active:
        state = GhostState(
            active=True,
            reason="manual",
            started_at=now,
            expected_end=None,
            review_completed_at=state.review_completed_at,
        )

    # Sprint 7 O1 — throttle tier from response-events.
    throttle_cap: Optional[int] = None
    throttle_reason: Optional[str] = None
    if not no_throttle:
        rate = acceptance_rate_from_events(
            paths.RESPONSE_EVENTS_PATH, window_days=14, now=now,
        )
        if rate is not None:
            if rate < 0.10:
                throttle_cap = 0
                throttle_reason = "throttle:very_low_acceptance"
            elif rate < 0.20:
                throttle_cap = 1
                throttle_reason = "throttle:low_acceptance"

    new_offers = rank_candidates(
        candidates,
        now=now,
        offers_log=offers,
        tombstones=tombs,
        weights=weights,
        recent_acceptance_rate=acceptance_rate,
        days_since_install=days_since_install,
        ghost_override=ghost,
        ritual=ritual,
        signal_index=sig_index,
        ghost_state=state,
        rejection_suppress_days=rejection_suppress_days,
        throttle_cap=throttle_cap,
        throttle_reason=throttle_reason,
        run_id=run_id,
    )
    for o in new_offers:
        append_jsonl(paths.OFFERS_PATH, o.to_dict())

    surfaced = sum(1 for o in new_offers if o.shown)
    ghost_n = sum(
        1 for o in new_offers
        if (o.hold_reason or "").startswith("ghost") or o.hold_reason == "ghost"
    )
    throttle_n = sum(
        1 for o in new_offers if (o.hold_reason or "").startswith("throttle")
    )
    dropped = sum(
        1 for o in new_offers
        if (not o.shown) and not (
            (o.hold_reason or "").startswith("ghost")
            or o.hold_reason == "ghost"
            or (o.hold_reason or "").startswith("throttle")
        )
    )
    msg = f"surfaced={surfaced} ghost={ghost_n} dropped={dropped}"
    if throttle_n:
        msg += f" throttled={throttle_n}"
    print(msg)
    return 0


def _load_offer_context(offer_id: str) -> tuple[Offer, Candidate, list[Signal]]:
    offers = [Offer.from_dict(r) for r in read_jsonl(paths.OFFERS_PATH)]
    offer = next((o for o in offers if o.offer_id == offer_id), None)
    if offer is None:
        raise SystemExit(f"offer not found: {offer_id}")
    cand: Optional[Candidate] = None
    if offer.candidate_id:
        for r in read_jsonl(paths.CANDIDATES_PATH):
            if r.get("candidate_id") == offer.candidate_id:
                cand = Candidate.from_dict(r)
                break
    if cand is None:
        # Synthesize a minimal Candidate from the Offer so drafting can still
        # proceed when the candidates log was rotated.
        cand = Candidate(
            candidate_id=offer.candidate_id or f"derived-from-{offer.offer_id}",
            type=offer.type,
            summary=offer.summary,
            cited_signals=list(offer.cited_signals),
            confidence=offer.score_components.get("confidence", 0.5),
            staleness_days=0,
            action_verb="draft",
        )
    cited_ids = set(offer.cited_signals)
    cited_signals: list[Signal] = []
    for r in read_jsonl(paths.SIGNALS_PATH):
        if r.get("signal_id") in cited_ids:
            cited_signals.append(Signal.from_dict(r))
    return offer, cand, cited_signals


def _cmd_draft_prompt(offer_id: Optional[str], all_offers: bool) -> int:
    identity = load_identity(paths.VAULT_ROOT)
    offers = [Offer.from_dict(r) for r in read_jsonl(paths.OFFERS_PATH)]
    if offer_id:
        targets = [o for o in offers if o.offer_id == offer_id]
        if not targets:
            print(f"offer not found: {offer_id}", file=sys.stderr)
            return 2
    else:
        # --all: only offers that have no draft yet.
        targets = [o for o in offers if not o.draft_artifact_path]

    if not targets:
        # Emit nothing — caller can treat empty stdout as "no work".
        return 0

    # For --all we print one JSON object per line (JSONL). For a single
    # offer we pretty-print for readability.
    pretty = offer_id is not None
    for o in targets:
        _o, cand, cited = _load_offer_context(o.offer_id)
        handshake = build_draft_prompt(o, cand, cited, identity)
        if pretty:
            print(json.dumps(handshake, indent=2, sort_keys=True))
        else:
            print(json.dumps(handshake, sort_keys=True))
    return 0


def _cmd_draft_apply(offer_id: str, input_path: str) -> int:
    offer, _cand, cited = _load_offer_context(offer_id)
    with open(input_path, "r", encoding="utf-8") as f:
        response = json.load(f)
    cited_ids = {s.signal_id for s in cited}
    draft, notes = apply_draft_response(response, offer, cited_ids)
    if draft is None:
        print("written=0 rejected=1")
        for n in notes:
            print(f"  reject: {n}", file=sys.stderr)
        return 1

    write_draft_file(draft, offer, paths.DRAFTS_DIR)

    # Update the offer row with draft_artifact_path (atomic rewrite).
    rows = read_jsonl(paths.OFFERS_PATH)
    for i, r in enumerate(rows):
        if r.get("offer_id") == offer_id:
            r["draft_artifact_path"] = draft.path
            rows[i] = r
            break
    rewrite_jsonl(paths.OFFERS_PATH, rows)

    print("written=1 rejected=0")
    for w in notes:
        print(f"  warn: {w}", file=sys.stderr)
    return 0


def _cmd_log(
    offer_id: str, response: str, reason: Optional[str], ghost_mode: bool
) -> int:
    try:
        record_response(
            offer_id,
            response,
            now=datetime.now(timezone.utc),
            offers_path=paths.OFFERS_PATH,
            tombstones_path=paths.TOMBSTONES_PATH,
            ghost_log_path=paths.GHOST_LOG_PATH,
            ghost_mode=ghost_mode,
            reason=reason,
            events_path=paths.RESPONSE_EVENTS_PATH,
        )
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"logged offer_id={offer_id} response={response}")
    return 0


def _cmd_acceptance_rate(window_days: int) -> int:
    offers = [Offer.from_dict(r) for r in read_jsonl(paths.OFFERS_PATH)]
    rate = compute_acceptance_rate(offers, window_days=window_days)
    if rate is None:
        print("insufficient_data")
    else:
        print(f"{rate:.6f}")
    return 0


def _cmd_replay(fixture_path: str, write_run: bool, as_json: bool) -> int:
    try:
        fixture = load_fixture(Path(fixture_path))
    except FixtureError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    result = run_replay(fixture, vault_root=paths.VAULT_ROOT, write_run=write_run)
    scorecard = score_fixture(result, fixture)
    calibration = compare_with_grades(scorecard, fixture.grades)

    if as_json:
        payload = {
            "fixture_id": fixture.fixture_id,
            "summary": result.to_summary(),
            "scorecard": scorecard.to_dict(),
            "calibration": calibration.to_dict(),
            "run_dir": str(result.run_dir) if result.run_dir else None,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    s = result.to_summary()
    print(f"replay fixture={fixture.fixture_id}")
    print(
        f"  candidates={s['n_candidates']} rejected={s['n_rejections']} "
        f"offers={s['n_offers']} surfaced={s['n_surfaced']} "
        f"ghost={s['n_ghost']} dropped={s['n_dropped']} "
        f"drafts={s['n_drafts']} draft_rejected={s['n_draft_rejections']}"
    )
    if result.rejections:
        first = result.rejections[0]
        print(f"  first_reject: {first.get('reason')} — {first.get('detail', '')}")
    print("  rubric_means:")
    for k in (
        "grounding",
        "specificity",
        "staleness",
        "novelty",
        "length_discipline",
        "citation_discipline",
        "overall",
    ):
        print(f"    {k}: {scorecard.means.get(k, 0.0):.3f}")
    if calibration.n > 0:
        r = calibration.pearson_r
        r_str = f"{r:.3f}" if r is not None else "undefined"
        print(f"  calibration: n={calibration.n} pearson_r={r_str}")
    else:
        print("  calibration: no_human_grades")
    if result.run_dir:
        print(f"  run_dir: {result.run_dir}")
    return 0


def _cmd_grade(
    fixture_path: str,
    offer_id: str,
    score: float,
    reason: str,
    grader: str,
) -> int:
    fp = Path(fixture_path)
    if not fp.is_dir():
        print(f"error: fixture not found: {fp}", file=sys.stderr)
        return 2
    if not (0.0 <= score <= 1.0):
        print(f"error: --score must be in [0,1], got {score}", file=sys.stderr)
        return 2
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    grade = Grade(
        offer_id=offer_id,
        human_score=float(score),
        reason=reason,
        graded_at=now_iso,
        grader=grader,
    )
    append_jsonl(fp / "grades.jsonl", grade.to_dict())
    print(f"graded offer_id={offer_id} score={score:.3f} grader={grader}")
    return 0


def _cmd_rubric_check(offer_id: str, as_json: bool) -> int:
    offers = [Offer.from_dict(r) for r in read_jsonl(paths.OFFERS_PATH)]
    target = next((o for o in offers if o.offer_id == offer_id), None)
    if target is None:
        print(f"error: offer not found: {offer_id}", file=sys.stderr)
        return 2
    cand: Optional[Candidate] = None
    if target.candidate_id:
        for r in read_jsonl(paths.CANDIDATES_PATH):
            if r.get("candidate_id") == target.candidate_id:
                cand = Candidate.from_dict(r)
                break
    cited_ids = set(target.cited_signals)
    all_signals = [Signal.from_dict(r) for r in read_jsonl(paths.SIGNALS_PATH)]
    cited_signals = [s for s in all_signals if s.signal_id in cited_ids]
    universe = {s.signal_id for s in all_signals}

    # Try to locate an existing draft artifact on disk and read its body.
    draft: Optional[Draft] = None
    if target.draft_artifact_path:
        p = paths.VAULT_ROOT / target.draft_artifact_path
        if p.exists():
            try:
                raw = p.read_text(encoding="utf-8")
                body = raw.split("---", 2)[-1].strip() if raw.startswith("---") else raw
                draft = Draft(
                    offer_id=target.offer_id,
                    draft_text=body,
                    citations=list(target.cited_signals),
                    confidence=target.score_components.get("confidence", 0.5),
                    warnings=[],
                    created_at=target.created_at,
                    path=target.draft_artifact_path,
                )
            except OSError:
                draft = None

    score = score_offer(
        target,
        cand,
        cited_signals,
        draft,
        prior_offers=[o for o in offers if o.offer_id != target.offer_id],
        signal_universe_ids=universe,
        now=datetime.now(timezone.utc),
    )

    if as_json:
        print(json.dumps(score.to_dict(), indent=2, sort_keys=True))
        return 0
    print(f"rubric-check offer_id={offer_id}")
    for dim in (
        "grounding",
        "specificity",
        "staleness",
        "novelty",
        "length_discipline",
        "citation_discipline",
        "overall",
    ):
        print(f"  {dim}: {getattr(score, dim):.3f}")
    return 0


def _cmd_ghost_status(as_json: bool, check_exit_ready: bool = False) -> int:
    install_date = read_install_date(paths.INSTALL_PATH)
    now = datetime.now(timezone.utc)
    state = compute_ghost_state(
        install_date=install_date,
        now=now,
        manual_yaml_path=paths.GHOST_MODE_PATH,
        ghost_review_log_path=paths.GHOST_LOG_PATH,
        post_review_pause_path=paths.POST_REVIEW_PAUSE_PATH,
    )
    payload: dict = {
        "install_date": install_date.isoformat(),
        "now": now.isoformat().replace("+00:00", "Z"),
        **state.to_dict(),
    }
    if check_exit_ready:
        from .ghost import check_ghost_exit_ready
        payload["exit_readiness"] = check_ghost_exit_ready(
            install_date=install_date,
            now=now,
            manual_yaml_path=paths.GHOST_MODE_PATH,
            ghost_review_log_path=paths.GHOST_LOG_PATH,
            post_review_pause_path=paths.POST_REVIEW_PAUSE_PATH,
            install_yaml_path=paths.INSTALL_PATH,
            response_events_path=paths.RESPONSE_EVENTS_PATH,
        )

    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"ghost active: {state.active}")
        print(f"reason: {state.reason or '-'}")
        print(f"install_date: {install_date.isoformat()}")
        if state.expected_end:
            print(f"expected_end: {state.expected_end.isoformat()}")
        if state.review_completed_at:
            print(f"last_review: {state.review_completed_at.isoformat()}")
        if check_exit_ready:
            er = payload["exit_readiness"]
            print(f"exit_ready: {er['ready']}")
            for k, v in er["predicates"].items():
                print(f"  {k}: {v}")
            print(f"  details:")
            for k, v in er["details"].items():
                print(f"    {k}: {v}")
    return 0


def _build_ghost_digest(window_days: int, now: datetime) -> tuple[str, GhostState, list[Offer]]:
    install_date = read_install_date(paths.INSTALL_PATH)
    state = compute_ghost_state(
        install_date=install_date,
        now=now,
        manual_yaml_path=paths.GHOST_MODE_PATH,
        ghost_review_log_path=paths.GHOST_LOG_PATH,
        post_review_pause_path=paths.POST_REVIEW_PAUSE_PATH,
    )
    offers = [Offer.from_dict(r) for r in read_jsonl(paths.OFFERS_PATH)]

    cutoff = now - timedelta(days=window_days)

    def _within_window(o: Offer) -> bool:
        # Best-effort parse of created_at
        ts = o.created_at
        if isinstance(ts, str) and ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(ts)
        except (TypeError, ValueError):
            return True  # don't drop on parse failure
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= cutoff

    held = [
        o for o in offers
        if ((o.hold_reason or "") == "ghost" or (o.hold_reason or "").startswith("ghost:"))
        and _within_window(o)
    ]

    # Build draft + signal lookups for the digest.
    drafts: dict[str, Draft] = {}
    for o in held:
        if o.draft_artifact_path:
            p = paths.VAULT_ROOT / o.draft_artifact_path
            if p.exists():
                try:
                    raw = p.read_text(encoding="utf-8")
                    body = raw.split("---", 2)[-1].strip() if raw.startswith("---") else raw
                    drafts[o.offer_id] = Draft(
                        offer_id=o.offer_id,
                        draft_text=body,
                        citations=list(o.cited_signals),
                        confidence=o.score_components.get("confidence", 0.5),
                        warnings=[],
                        created_at=o.created_at,
                        path=o.draft_artifact_path,
                    )
                except OSError:
                    pass

    cited_ids: set[str] = set()
    for o in held:
        cited_ids.update(o.cited_signals)
    signal_lookup: dict[str, Signal] = {}
    if cited_ids:
        for r in read_jsonl(paths.SIGNALS_PATH):
            sid = r.get("signal_id")
            if sid in cited_ids:
                signal_lookup[sid] = Signal.from_dict(r)

    content = render_ghost_digest(
        offers=held,
        drafts=drafts,
        cited_signals_lookup=signal_lookup,
        ghost_state=state,
        now=now,
    )
    return content, state, held


def _cmd_ghost_review(
    window_days: int, no_write: bool, mark_complete: bool, notes: Optional[str]
) -> int:
    now = datetime.now(timezone.utc)
    content, _state, held = _build_ghost_digest(window_days=window_days, now=now)
    print(content)
    if not no_write:
        archive = paths.ACTIVATION_DIR / f"ghost-review-{now.strftime('%Y%m%d')}.md"
        write_ghost_digest(content, archive)
        print(f"# wrote {archive}", file=sys.stderr)
    if mark_complete:
        decisions = [
            {
                "offer_id": o.offer_id,
                "user_response": o.user_response,
                "reason": o.response_reason,
            }
            for o in held
        ]
        mark_ghost_review_complete(
            paths.GHOST_LOG_PATH, now=now, decisions=decisions, notes=notes
        )
        print(
            f"# ghost-review-complete marker appended to {paths.GHOST_LOG_PATH}",
            file=sys.stderr,
        )
    return 0


def _cmd_ghost_exit(acknowledge: bool, force: bool = False) -> int:
    if not acknowledge:
        print(
            "error: ghost-exit requires --acknowledge (no accidental exits).",
            file=sys.stderr,
        )
        return 1

    install_date = read_install_date(paths.INSTALL_PATH)
    now = datetime.now(timezone.utc)

    from .ghost import check_ghost_exit_ready

    readiness = check_ghost_exit_ready(
        install_date=install_date,
        now=now,
        manual_yaml_path=paths.GHOST_MODE_PATH,
        ghost_review_log_path=paths.GHOST_LOG_PATH,
        post_review_pause_path=paths.POST_REVIEW_PAUSE_PATH,
        install_yaml_path=paths.INSTALL_PATH,
        response_events_path=paths.RESPONSE_EVENTS_PATH,
    )

    if not readiness["ready"] and not force:
        print("ghost-exit refused — readiness predicates not all met:", file=sys.stderr)
        for k, v in readiness["predicates"].items():
            mark = "PASS" if v else "FAIL"
            print(f"  [{mark}] {k}", file=sys.stderr)
        for k, v in readiness["details"].items():
            print(f"    {k}: {v}", file=sys.stderr)
        print("Use --force to override after manual audit.", file=sys.stderr)
        return 1

    # Idempotent: write/refresh ghost_exited_at.
    write_install_field(
        paths.INSTALL_PATH, "ghost_exited_at",
        now.isoformat().replace("+00:00", "Z"),
    )
    print(f"ghost-exit ok: ghost_exited_at written to {paths.INSTALL_PATH}")
    return 0


def _cmd_handshake_gc(older_than_days: int, as_json: bool) -> int:
    from .handshake import gc_handshakes
    deleted = gc_handshakes(paths.HANDSHAKES_DIR, older_than_days=older_than_days)
    if as_json:
        print(json.dumps({"deleted": [str(p) for p in deleted], "count": len(deleted)},
                         indent=2, sort_keys=True))
    else:
        print(f"deleted {len(deleted)} handshake(s) older than {older_than_days}d")
        for p in deleted:
            print(f"  {p}")
    return 0


def _cmd_policy_check(acknowledge: bool, as_json: bool) -> int:
    from .policy import policy_check
    result = policy_check(
        vault_root=paths.VAULT_ROOT,
        state_path=paths.POLICY_STATE_PATH,
        pause_path=paths.POST_REVIEW_PAUSE_PATH,
        now=datetime.now(timezone.utc),
        acknowledge=acknowledge,
    )
    payload = {
        "current_hash": result.current_hash,
        "previous_hash": result.previous_hash,
        "changed": result.changed,
        "pause_until": result.pause_until.isoformat() if result.pause_until else None,
        "notice": result.notice,
    }
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for k, v in payload.items():
            print(f"{k}: {v}")
    return 0


def _cmd_weekly_metrics(week_ending: Optional[str], as_json: bool) -> int:
    from .metrics import weekly_metrics
    we_date = None
    if week_ending:
        try:
            we_date = date.fromisoformat(week_ending)
        except ValueError:
            print(f"error: --week-ending must be YYYY-MM-DD, got {week_ending!r}",
                  file=sys.stderr)
            return 2
    wm = weekly_metrics(vault_root=paths.VAULT_ROOT, week_ending=we_date)
    if as_json:
        print(json.dumps(wm.to_dict(), indent=2, sort_keys=True))
    else:
        d = wm.to_dict()
        print(f"weekly metrics — week ending {d['week_ending']}")
        for k, v in d.items():
            if k == "week_ending":
                continue
            print(f"  {k}: {v}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command not in (
        "run", "gather", "extract-prompt", "extract-apply", "rank",
        "draft-prompt", "draft-apply", "log", "acceptance-rate",
        "replay", "grade", "rubric-check",
        "ghost-status", "ghost-review", "ghost-exit",
        "handshake-gc", "policy-check", "weekly-metrics",
    ):
        parser.error(f"unknown command: {args.command}")
        return 2

    # Kill switch: honored first, before anything else.
    killed, kill_reason = kill_status()
    if killed:
        if kill_reason:
            print(f"kill-switch engaged: {kill_reason} — exiting")
        else:
            print("kill-switch engaged — exiting")
        return 0

    # Quiet-mode: gates writes. Read-only ghost-status / ghost-review still
    # run so the user can audit without disabling quiet-mode.
    quiet, quiet_reason, until = quiet_status()
    if quiet and args.command not in (
        "ghost-status", "ghost-review", "policy-check", "weekly-metrics",
    ):
        until_str = until.isoformat() if until else "?"
        tail = f" ({quiet_reason})" if quiet_reason else ""
        print(f"quiet mode until {until_str}{tail} — exiting")
        return 0

    if args.command == "gather":
        return _cmd_gather(dry_run=args.dry_run)

    if args.command == "extract-prompt":
        return _cmd_extract_prompt(
            batch_size=args.batch_size,
            signals_path=args.signals_path,
            batch_index=args.batch_index,
        )

    if args.command == "extract-apply":
        return _cmd_extract_apply(
            input_path=args.input,
            batch_id=args.batch_id,
            signals_path=args.signals_path,
            run_id=args.run_id,
            no_grounding_gate=args.no_grounding_gate,
        )

    if args.command == "rank":
        return _cmd_rank(
            days_since_install=args.days_since_install,
            acceptance_rate=args.acceptance_rate,
            ghost=args.ghost,
            ritual=args.ritual,
            run_id=args.run_id,
            no_throttle=args.no_throttle,
            no_run_filter=args.no_run_filter,
            rejection_suppress_days=args.rejection_suppress_days,
        )

    if args.command == "draft-prompt":
        return _cmd_draft_prompt(
            offer_id=args.offer_id,
            all_offers=args.all,
        )

    if args.command == "draft-apply":
        return _cmd_draft_apply(offer_id=args.offer_id, input_path=args.input)

    if args.command == "log":
        return _cmd_log(
            offer_id=args.offer_id,
            response=args.response,
            reason=args.reason,
            ghost_mode=args.ghost,
        )

    if args.command == "acceptance-rate":
        return _cmd_acceptance_rate(window_days=args.window_days)

    if args.command == "replay":
        return _cmd_replay(
            fixture_path=args.fixture,
            write_run=args.write_run,
            as_json=args.json,
        )

    if args.command == "grade":
        return _cmd_grade(
            fixture_path=args.fixture,
            offer_id=args.offer_id,
            score=args.score,
            reason=args.reason,
            grader=args.grader,
        )

    if args.command == "rubric-check":
        return _cmd_rubric_check(offer_id=args.offer_id, as_json=args.json)

    if args.command == "ghost-status":
        return _cmd_ghost_status(as_json=args.json, check_exit_ready=args.check_exit_ready)

    if args.command == "ghost-review":
        return _cmd_ghost_review(
            window_days=args.window_days,
            no_write=args.no_write,
            mark_complete=args.mark_complete,
            notes=args.notes,
        )

    if args.command == "ghost-exit":
        return _cmd_ghost_exit(acknowledge=args.acknowledge, force=args.force)

    if args.command == "handshake-gc":
        return _cmd_handshake_gc(
            older_than_days=args.older_than_days, as_json=args.json,
        )

    if args.command == "policy-check":
        return _cmd_policy_check(acknowledge=args.acknowledge, as_json=args.json)

    if args.command == "weekly-metrics":
        return _cmd_weekly_metrics(week_ending=args.week_ending, as_json=args.json)

    # command == "run"
    if args.dry_run:
        _print_dry_run_summary()
        return 0

    print(
        "pipeline not yet wired, current sprint: 2 of 7"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
