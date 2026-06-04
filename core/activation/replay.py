"""Offline replay harness for the B-1 Activation Engine (Sprint 5).

Per design doc §12 step 4 and §9.1, the replay harness is the calibration
instrument: it runs the full pipeline against pre-recorded signal + LLM
fixtures without touching the real vault or the network. This is how the user
grades offers, and eventually how Amp self-scores its own output
(§10 locked decision #4).

A fixture is a directory under ``System/activation/replay/fixtures/<id>/``
containing:

    meta.yaml              — id, description, created_at, now (frozen clock),
                             days_since_install, acceptance_rate (or null),
                             ghost (bool, optional).
    signals.jsonl          — input signals for the pipeline.
    extract_response.json  — pre-recorded LLM handshake response
                             (a JSON array of candidate dicts).
    draft_responses/       — optional; one {offer_id}.json per drafted offer.
    offers.jsonl           — optional prior offers (for recent-offer penalty).
    tombstones.jsonl       — optional prior tombstones.
    grades.jsonl           — optional human grades for this fixture.

``run_replay`` returns a ``ReplayResult`` with everything the rubric needs.
``--write-run`` materializes the run under
``<vault_root>/System/activation/replay/runs/<fixture_id>/<stamp>/``.
Without it the whole run is in-memory — the real vault is *never* touched.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import yaml

from . import paths as _paths  # used only for defaults; not mutated
from .config import load_weights
from .draft import apply_draft_response
from .extract import apply_extract_response, batch_signals, make_batch_id
from .rank import rank as rank_candidates
from .schemas import Candidate, Draft, Grade, Offer, Signal, Tombstone


# --------------------------------------------------------------------------
# Dataclasses
# --------------------------------------------------------------------------


@dataclass
class Fixture:
    fixture_id: str
    fixture_path: Path
    meta: Dict[str, Any]
    signals: List[Signal]
    extract_response: List[Dict[str, Any]]
    draft_responses: Dict[str, Dict[str, Any]]
    prior_offers: List[Offer]
    prior_tombstones: List[Tombstone]
    grades: List[Grade]

    def now(self) -> datetime:
        raw = self.meta.get("now")
        if isinstance(raw, datetime):
            dt = raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
            return dt
        if isinstance(raw, date):
            return datetime(raw.year, raw.month, raw.day, tzinfo=timezone.utc)
        if isinstance(raw, str):
            s = raw.strip()
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            try:
                dt = datetime.fromisoformat(s)
            except ValueError as e:
                raise FixtureError(f"meta.now: invalid ISO timestamp: {raw!r}") from e
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        raise FixtureError("meta.now is required (ISO-8601 string)")

    @property
    def days_since_install(self) -> int:
        v = self.meta.get("days_since_install")
        if not isinstance(v, int) or isinstance(v, bool):
            raise FixtureError("meta.days_since_install must be an int")
        return v

    @property
    def acceptance_rate(self) -> Optional[float]:
        v = self.meta.get("acceptance_rate", None)
        if v is None:
            return None
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise FixtureError("meta.acceptance_rate must be a number or null")
        return float(v)

    @property
    def ghost(self) -> bool:
        return bool(self.meta.get("ghost", False))


@dataclass
class ReplayResult:
    fixture_id: str
    candidates: List[Candidate]
    rejections: List[Dict[str, Any]]
    offers: List[Offer]
    drafts: List[Draft]
    draft_rejections: List[Dict[str, Any]] = field(default_factory=list)
    timings: Dict[str, float] = field(default_factory=dict)
    run_dir: Optional[Path] = None

    def to_summary(self) -> Dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "n_candidates": len(self.candidates),
            "n_rejections": len(self.rejections),
            "n_offers": len(self.offers),
            "n_surfaced": sum(1 for o in self.offers if o.shown),
            "n_ghost": sum(1 for o in self.offers if o.hold_reason == "ghost"),
            "n_dropped": sum(
                1 for o in self.offers if (not o.shown) and o.hold_reason != "ghost"
            ),
            "n_drafts": len(self.drafts),
            "n_draft_rejections": len(self.draft_rejections),
            "timings": dict(self.timings),
        }


class FixtureError(ValueError):
    """Raised when a fixture cannot be loaded or is malformed."""


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


_REQUIRED_META_KEYS = ("id", "description", "now", "days_since_install")


def _read_jsonl_strict(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            s = raw.strip()
            if not s:
                continue
            try:
                out.append(json.loads(s))
            except json.JSONDecodeError as e:
                raise FixtureError(
                    f"{path}: invalid JSON on line {lineno}: {e}"
                ) from e
    return out


def load_fixture(fixture_path: Path) -> Fixture:
    """Load a fixture directory into a ``Fixture``. Raises on malformed input."""
    fixture_path = Path(fixture_path)
    if not fixture_path.is_dir():
        raise FixtureError(f"fixture path is not a directory: {fixture_path}")

    meta_path = fixture_path / "meta.yaml"
    if not meta_path.exists():
        raise FixtureError(f"missing meta.yaml: {meta_path}")
    try:
        with meta_path.open("r", encoding="utf-8") as f:
            meta = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise FixtureError(f"meta.yaml: invalid YAML: {e}") from e
    if not isinstance(meta, dict):
        raise FixtureError("meta.yaml: top level must be a mapping")
    for k in _REQUIRED_META_KEYS:
        if k not in meta:
            raise FixtureError(f"meta.yaml: missing required key {k!r}")

    # Signals
    signals_path = fixture_path / "signals.jsonl"
    if not signals_path.exists():
        raise FixtureError(f"missing signals.jsonl: {signals_path}")
    raw_sigs = _read_jsonl_strict(signals_path)
    signals = [Signal.from_dict(r) for r in raw_sigs]

    # Extract response
    er_path = fixture_path / "extract_response.json"
    if not er_path.exists():
        raise FixtureError(f"missing extract_response.json: {er_path}")
    try:
        with er_path.open("r", encoding="utf-8") as f:
            er = json.load(f)
    except json.JSONDecodeError as e:
        raise FixtureError(f"extract_response.json: invalid JSON: {e}") from e
    if not isinstance(er, list):
        raise FixtureError("extract_response.json: top level must be a list")

    # Draft responses (optional)
    drafts_dir = fixture_path / "draft_responses"
    draft_responses: Dict[str, Dict[str, Any]] = {}
    if drafts_dir.is_dir():
        for p in sorted(drafts_dir.glob("*.json")):
            try:
                with p.open("r", encoding="utf-8") as f:
                    draft_responses[p.stem] = json.load(f)
            except json.JSONDecodeError as e:
                raise FixtureError(f"{p}: invalid JSON: {e}") from e

    # Optional priors
    prior_offers_path = fixture_path / "offers.jsonl"
    prior_offers: List[Offer] = []
    if prior_offers_path.exists():
        prior_offers = [Offer.from_dict(r) for r in _read_jsonl_strict(prior_offers_path)]

    prior_tombs_path = fixture_path / "tombstones.jsonl"
    prior_tombs: List[Tombstone] = []
    if prior_tombs_path.exists():
        prior_tombs = [Tombstone.from_dict(r) for r in _read_jsonl_strict(prior_tombs_path)]

    grades_path = fixture_path / "grades.jsonl"
    grades: List[Grade] = []
    if grades_path.exists():
        grades = [Grade.from_dict(r) for r in _read_jsonl_strict(grades_path)]

    fid = str(meta.get("id") or fixture_path.name)
    return Fixture(
        fixture_id=fid,
        fixture_path=fixture_path,
        meta=meta,
        signals=signals,
        extract_response=er,
        draft_responses=draft_responses,
        prior_offers=prior_offers,
        prior_tombstones=prior_tombs,
        grades=grades,
    )


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------


def run_replay(
    fixture: Fixture,
    *,
    vault_root: Optional[Path] = None,
    write_run: bool = False,
    weights: Optional[Dict[str, float]] = None,
) -> ReplayResult:
    """Run the pipeline deterministically against a fixture.

    Read-only on the real vault unless ``write_run`` is True, in which case a
    scoped subdirectory is created under
    ``<vault_root>/System/activation/replay/runs/<fixture_id>/<stamp>/``.
    ``signals.jsonl``, ``offers.jsonl``, ``tombstones.jsonl``, etc. in the
    live activation dir are *never* written.
    """
    now_clock = fixture.now()
    timings: Dict[str, float] = {}

    # Stage 2 — extract-apply on the first batch (test fixtures are small;
    # candidate responses are provided as a single list).
    t0 = time.monotonic()
    batches = batch_signals(fixture.signals, max_size=max(1, len(fixture.signals) or 1))
    batch = batches[0] if batches else []
    batch_id = make_batch_id(now_clock.date(), 0)
    candidates, rejections = apply_extract_response(
        fixture.extract_response, batch, batch_id
    )
    timings["extract_s"] = round(time.monotonic() - t0, 6)

    # Stage 3 — rank. Replay runs always use an empty offers_log coming in
    # *from the current run*; prior_offers (from fixture) are passed as the
    # offers_log so the recent-offer penalty can be exercised.
    weights_in = weights if weights is not None else load_weights()
    t0 = time.monotonic()
    offers = rank_candidates(
        candidates,
        now=now_clock,
        offers_log=list(fixture.prior_offers),
        tombstones=list(fixture.prior_tombstones),
        weights=weights_in,
        recent_acceptance_rate=fixture.acceptance_rate,
        days_since_install=fixture.days_since_install,
        ghost_override=fixture.ghost,
        run_id=f"replay-{fixture.fixture_id}",
        ritual="daily-plan",
        signal_index={s.signal_id: s.timestamp for s in fixture.signals},
    )
    timings["rank_s"] = round(time.monotonic() - t0, 6)

    # Stage 4 — apply recorded draft responses for any matching offer.
    sig_by_id = {s.signal_id: s for s in fixture.signals}
    drafts: List[Draft] = []
    draft_rejections: List[Dict[str, Any]] = []
    t0 = time.monotonic()
    for offer in offers:
        resp = fixture.draft_responses.get(offer.offer_id)
        if resp is None:
            continue
        cited_ids = {c for c in offer.cited_signals if c in sig_by_id}
        draft, notes = apply_draft_response(resp, offer, cited_ids)
        if draft is None:
            draft_rejections.append({"offer_id": offer.offer_id, "reasons": notes})
            continue
        drafts.append(draft)
    timings["draft_s"] = round(time.monotonic() - t0, 6)

    run_dir: Optional[Path] = None
    if write_run:
        vr = Path(vault_root) if vault_root is not None else _paths.VAULT_ROOT
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = vr / "System" / "activation" / "replay" / "runs" / fixture.fixture_id / stamp
        run_dir.mkdir(parents=True, exist_ok=True)
        _write_run(
            run_dir,
            fixture=fixture,
            candidates=candidates,
            rejections=rejections,
            offers=offers,
            drafts=drafts,
            draft_rejections=draft_rejections,
            timings=timings,
        )

    return ReplayResult(
        fixture_id=fixture.fixture_id,
        candidates=candidates,
        rejections=rejections,
        offers=offers,
        drafts=drafts,
        draft_rejections=draft_rejections,
        timings=timings,
        run_dir=run_dir,
    )


def _write_run(
    run_dir: Path,
    *,
    fixture: Fixture,
    candidates: Sequence[Candidate],
    rejections: Sequence[Dict[str, Any]],
    offers: Sequence[Offer],
    drafts: Sequence[Draft],
    draft_rejections: Sequence[Dict[str, Any]],
    timings: Dict[str, float],
) -> None:
    """Materialize a replay run to disk under ``run_dir`` (scoped path)."""
    def _dump_jsonl(name: str, rows: Sequence[Dict[str, Any]]) -> None:
        with (run_dir / name).open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")

    _dump_jsonl("candidates.jsonl", [c.to_dict() for c in candidates])
    _dump_jsonl("offers.jsonl", [o.to_dict() for o in offers])
    _dump_jsonl("drafts.jsonl", [d.to_dict() for d in drafts])
    _dump_jsonl("rejections.jsonl", list(rejections))
    _dump_jsonl("draft_rejections.jsonl", list(draft_rejections))
    (run_dir / "meta.json").write_text(
        json.dumps(
            {
                "fixture_id": fixture.fixture_id,
                "fixture_path": str(fixture.fixture_path),
                "timings": timings,
                "wrote_at": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


__all__ = [
    "Fixture",
    "FixtureError",
    "ReplayResult",
    "load_fixture",
    "run_replay",
]
