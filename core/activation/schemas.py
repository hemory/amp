"""Lightweight dataclass-based schemas for activation records.

Stdlib only. No pydantic dependency.

Schemas match §4.2, §4.5, §5.2, §6.4 of the B-1 design doc. Only fields
required for Sprint 1 scaffolding and subsequent sprints' persistence are
captured here; enrichment (score_components etc.) can be added without
breaking existing records because dict round-trip ignores unknown keys
only when explicitly noted — here we do NOT silently drop unknown keys.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any, ClassVar, Dict, List, Optional, Tuple


class SchemaError(ValueError):
    """Raised when a record fails schema validation."""


# Closed enums per §4.2 / §4.4 / §4.5 of design doc.
OFFER_TYPES: Tuple[str, ...] = (
    "meeting_followup",
    "commitment_reminder",
    "draft_request",
    "risk_flag",
    "person_reconnect",
    "prep_draft",
    "contradiction",
)
ACTION_VERBS: Tuple[str, ...] = ("draft", "send", "schedule", "review", "decide")
USER_RESPONSES: Tuple[Optional[str], ...] = (
    None,
    "accepted",
    "accepted_with_edits",
    "rejected",
    "never_again",
    "snoozed",
    "ignored",
    "viewed",
)
HOLD_REASONS: Tuple[Optional[str], ...] = (
    None,
    "budget",
    "throttle",
    "throttle:low_acceptance",
    "throttle:very_low_acceptance",
    "tombstoned",
    "ghost",
    "ghost:install_window",
    "ghost:manual",
    "ghost:post_review_pause",
    "no_citation",
    "ungrounded",
    "suppressed:accepted",
    "suppressed:rejected",
)
RITUALS: Tuple[str, ...] = ("daily-plan", "week-plan", "week-review", "meeting-prep")


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise SchemaError(msg)


def _require_type(value: Any, expected: type, field_name: str) -> None:
    if not isinstance(value, expected):
        raise SchemaError(
            f"field {field_name!r}: expected {expected.__name__}, got {type(value).__name__}"
        )


def _require_list_of_str(value: Any, field_name: str) -> None:
    _require_type(value, list, field_name)
    for i, item in enumerate(value):
        if not isinstance(item, str):
            raise SchemaError(f"field {field_name!r}[{i}]: expected str, got {type(item).__name__}")


@dataclass
class Signal:
    """A raw signal produced by Stage 1 (Gather). §4.1."""

    signal_id: str
    source: str  # e.g. "meeting_notes", "person_pages", "calendar"
    path: str
    timestamp: str  # ISO-8601
    excerpt: str
    # Optional structured payload — e.g. frontmatter fields extracted from
    # meeting notes (`calendar_event_id`, `attendees`, `meeting_date`).
    # Sprint 3's extractor uses this for precise meeting → calendar matching.
    # Kept out of to_dict() when None so rows stay compact and existing
    # non-meeting signal round-trips continue to compare equal.
    structured: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        if out.get("structured") is None:
            out.pop("structured", None)
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Signal":
        cls.validate(data)
        known = {f.name for f in fields(cls)}
        return cls(**{k: data[k] for k in known if k in data})

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> None:
        _require(isinstance(data, dict), "Signal: top-level must be a mapping")
        for name in ("signal_id", "source", "path", "timestamp", "excerpt"):
            _require(name in data, f"Signal: missing required field {name!r}")
            _require_type(data[name], str, name)
        _require(len(data["signal_id"]) > 0, "Signal: signal_id must be non-empty")
        if "structured" in data and data["structured"] is not None:
            _require_type(data["structured"], dict, "structured")


@dataclass
class Candidate:
    """A possible offer produced by Stage 2 (Extract). §4.2."""

    candidate_id: str
    type: str
    summary: str
    cited_signals: List[str]
    confidence: float
    staleness_days: int
    action_verb: str
    # Sprint 7 — run lineage. Defaulted here so existing constructions keep
    # working; extract stamps real values via apply_extract_response(run_id=).
    run_id: str = "legacy"
    batch_id: str = "legacy"
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Suppress sentinel lineage so legacy roundtrips (Sprint 1-6 fixtures)
        # remain byte-identical. Stamped lineage from Sprint 7+ is preserved.
        if d.get("run_id") == "legacy":
            d.pop("run_id", None)
        if d.get("batch_id") == "legacy":
            d.pop("batch_id", None)
        if d.get("created_at") == "":
            d.pop("created_at", None)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Candidate":
        cls.validate(data)
        known = {f.name for f in fields(cls)}
        # Back-compat for Sprint 1-6 candidates without lineage fields.
        kwargs = {k: data[k] for k in known if k in data}
        kwargs.setdefault("run_id", "legacy")
        kwargs.setdefault("batch_id", "legacy")
        kwargs.setdefault("created_at", "")
        return cls(**kwargs)

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> None:
        _require(isinstance(data, dict), "Candidate: top-level must be a mapping")
        for name in ("candidate_id", "type", "summary", "action_verb"):
            _require(name in data, f"Candidate: missing required field {name!r}")
            _require_type(data[name], str, name)
        _require(
            data["type"] in OFFER_TYPES,
            f"Candidate: type {data['type']!r} not in {OFFER_TYPES}",
        )
        _require(
            data["action_verb"] in ACTION_VERBS,
            f"Candidate: action_verb {data['action_verb']!r} not in {ACTION_VERBS}",
        )
        _require("cited_signals" in data, "Candidate: missing 'cited_signals'")
        _require_list_of_str(data["cited_signals"], "cited_signals")
        # Citation-required gate is enforced at extract-time (§4.2); schema
        # validation also forbids empty citations to be safe.
        _require(len(data["cited_signals"]) > 0, "Candidate: cited_signals must be non-empty")
        _require("confidence" in data, "Candidate: missing 'confidence'")
        _require(
            isinstance(data["confidence"], (int, float)) and not isinstance(data["confidence"], bool),
            "Candidate: confidence must be a number",
        )
        _require(0.0 <= float(data["confidence"]) <= 1.0, "Candidate: confidence must be in [0,1]")
        _require("staleness_days" in data, "Candidate: missing 'staleness_days'")
        _require(
            isinstance(data["staleness_days"], int) and not isinstance(data["staleness_days"], bool),
            "Candidate: staleness_days must be int",
        )


@dataclass
class Offer:
    """A surfaced (or held-back) offer produced by Stages 4–5. §5.2."""

    offer_id: str
    created_at: str
    ritual: str
    type: str
    shown: bool
    summary: str
    cited_signals: List[str]
    score: float
    candidate_id: Optional[str] = None
    hold_reason: Optional[str] = None
    draft_artifact_path: Optional[str] = None
    score_components: Dict[str, float] = field(default_factory=dict)
    user_response: Optional[str] = None
    response_timestamp: Optional[str] = None
    time_to_response_s: Optional[int] = None
    edit_distance_if_accepted: Optional[int] = None
    notes: Optional[str] = None
    response_reason: Optional[str] = None
    # Sprint 7 additions
    grounding_score: Optional[float] = None
    policy_hash: Optional[str] = None
    handshake_id: Optional[str] = None
    run_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        # Suppress optional-None fields so older Offer rows round-trip unchanged.
        for opt in (
            "response_reason",
            "grounding_score",
            "policy_hash",
            "handshake_id",
            "run_id",
        ):
            if out.get(opt) is None:
                out.pop(opt, None)
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Offer":
        cls.validate(data)
        known = {f.name for f in fields(cls)}
        kwargs = {k: data[k] for k in known if k in data}
        return cls(**kwargs)

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> None:
        _require(isinstance(data, dict), "Offer: top-level must be a mapping")
        for name in ("offer_id", "created_at", "ritual", "type", "summary"):
            _require(name in data, f"Offer: missing required field {name!r}")
            _require_type(data[name], str, name)
        _require(
            data["ritual"] in RITUALS, f"Offer: ritual {data['ritual']!r} not in {RITUALS}"
        )
        _require(
            data["type"] in OFFER_TYPES, f"Offer: type {data['type']!r} not in {OFFER_TYPES}"
        )
        _require("shown" in data and isinstance(data["shown"], bool), "Offer: 'shown' must be bool")
        _require("cited_signals" in data, "Offer: missing 'cited_signals'")
        _require_list_of_str(data["cited_signals"], "cited_signals")
        _require("score" in data, "Offer: missing 'score'")
        _require(
            isinstance(data["score"], (int, float)) and not isinstance(data["score"], bool),
            "Offer: score must be a number",
        )
        if "user_response" in data:
            _require(
                data["user_response"] in USER_RESPONSES,
                f"Offer: user_response {data['user_response']!r} not in {USER_RESPONSES}",
            )
        if "hold_reason" in data:
            _require(
                data["hold_reason"] in HOLD_REASONS,
                f"Offer: hold_reason {data['hold_reason']!r} not in {HOLD_REASONS}",
            )


@dataclass
class Tombstone:
    """A 'never suggest this again' marker. §6.4."""

    tombstone_id: str
    created_at: str
    type: str
    pattern: str
    source_offer_id: Optional[str] = None
    notes: Optional[str] = None
    # TTL in days. None ≡ effectively infinite (rank.py substitutes a very
    # large default). Sprint 3 stored this loosely on the dict; Sprint 4
    # promotes it to a first-class field.
    ttl_days: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        if out.get("ttl_days") is None:
            out.pop("ttl_days", None)
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Tombstone":
        cls.validate(data)
        known = {f.name for f in fields(cls)}
        kwargs = {k: data[k] for k in known if k in data}
        return cls(**kwargs)

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> None:
        _require(isinstance(data, dict), "Tombstone: top-level must be a mapping")
        for name in ("tombstone_id", "created_at", "type", "pattern"):
            _require(name in data, f"Tombstone: missing required field {name!r}")
            _require_type(data[name], str, name)
        _require(
            data["type"] in OFFER_TYPES,
            f"Tombstone: type {data['type']!r} not in {OFFER_TYPES}",
        )
        if "ttl_days" in data and data["ttl_days"] is not None:
            _require(
                isinstance(data["ttl_days"], int) and not isinstance(data["ttl_days"], bool),
                "Tombstone: ttl_days must be int or null",
            )
            _require(data["ttl_days"] >= 0, "Tombstone: ttl_days must be >= 0")


@dataclass
class Grade:
    """A human (or Amp-self) grade on a single Offer. Feeds rubric calibration.

    Added in Sprint 5 for the offline replay harness. ``human_score`` is a
    0..1 float (same scale as rubric.overall) so they can be correlated
    directly. ``grader`` is the free-form identity of the grader
    (convention: "user" for the human, "amp" once the rubric is
    self-applied per §10 locked decision #4).
    """

    offer_id: str
    human_score: float
    reason: str
    graded_at: str  # ISO-8601 string for JSONL round-trip
    grader: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Grade":
        cls.validate(data)
        known = {f.name for f in fields(cls)}
        return cls(**{k: data[k] for k in known if k in data})

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> None:
        _require(isinstance(data, dict), "Grade: top-level must be a mapping")
        for name in ("offer_id", "reason", "graded_at", "grader"):
            _require(name in data, f"Grade: missing required field {name!r}")
            _require_type(data[name], str, name)
        _require("human_score" in data, "Grade: missing 'human_score'")
        hs = data["human_score"]
        _require(
            isinstance(hs, (int, float)) and not isinstance(hs, bool),
            "Grade: human_score must be a number",
        )
        _require(0.0 <= float(hs) <= 1.0, "Grade: human_score must be in [0,1]")
        _require(len(data["offer_id"]) > 0, "Grade: offer_id must be non-empty")
        _require(len(data["grader"]) > 0, "Grade: grader must be non-empty")


@dataclass
class Draft:
    """An LLM-drafted artifact attached to an Offer. §4.4."""

    offer_id: str
    draft_text: str
    citations: List[str]
    confidence: float
    warnings: List[str]
    created_at: str  # ISO-8601
    path: str  # relative path under System/activation/drafts/

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Draft":
        cls.validate(data)
        known = {f.name for f in fields(cls)}
        return cls(**{k: data[k] for k in known if k in data})

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> None:
        _require(isinstance(data, dict), "Draft: top-level must be a mapping")
        for name in ("offer_id", "draft_text", "created_at", "path"):
            _require(name in data, f"Draft: missing required field {name!r}")
            _require_type(data[name], str, name)
        _require("citations" in data, "Draft: missing 'citations'")
        _require_list_of_str(data["citations"], "citations")
        _require("warnings" in data, "Draft: missing 'warnings'")
        _require_list_of_str(data["warnings"], "warnings")
        _require("confidence" in data, "Draft: missing 'confidence'")
        _require(
            isinstance(data["confidence"], (int, float)) and not isinstance(data["confidence"], bool),
            "Draft: confidence must be a number",
        )
        _require(0.0 <= float(data["confidence"]) <= 1.0, "Draft: confidence must be in [0,1]")


@dataclass
class Event:
    """An append-only response event row. Sprint 7 H3.

    Persisted to ``System/activation/response-events.jsonl`` (gitignored).
    The Offer row's ``user_response`` is the *latest* state; this log is the
    history. Every call to ``record_response`` appends one Event.
    """

    event_id: str
    offer_id: str
    response: str
    timestamp: str  # ISO-8601
    mode: str  # "ghost" | "live"
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        if out.get("reason") is None:
            out.pop("reason", None)
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        known = {f.name for f in fields(cls)}
        return cls(**{k: data[k] for k in known if k in data})


@dataclass
class Handshake:
    """Snapshot artifact that pins an LLM handshake to a frozen world.

    Persisted under ``System/activation/handshakes/``. Both extract and draft
    handshakes share this shape; ``stage`` distinguishes them.
    """

    handshake_id: str
    stage: str  # "extract" | "draft"
    created_at: str
    schema_version: str
    prompt_text: str
    prompt_hash: str
    weights_hash: str
    identity_hash: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Handshake":
        known = {f.name for f in fields(cls)}
        return cls(**{k: data[k] for k in known if k in data})


@dataclass
class GroundingResult:
    passed: bool
    overlap_ratio: float
    anchored_tokens: int
    total_tokens: int
    unanchored_tokens: List[str] = field(default_factory=list)
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WeeklyMetrics:
    """Weekly review metrics. Sprint 7 O4."""

    week_ending: str  # YYYY-MM-DD
    offers_proposed: int
    offers_surfaced: int
    offers_held_ghost: int
    accepted: int
    rejected: int
    never_again_count: int
    snoozed: int
    ignored: int
    draft_count: int
    draft_adopted_count: int
    median_response_seconds: Optional[float]
    p95_response_seconds: Optional[float]
    mean_edit_distance: Optional[float]
    grounding_pass_rate: Optional[float]
    citation_pass_rate: Optional[float]
    throttle_active_days: int
    ghost_active_days: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


__all__ = [
    "SchemaError",
    "Signal",
    "Candidate",
    "Offer",
    "Tombstone",
    "Draft",
    "Grade",
    "Event",
    "Handshake",
    "GroundingResult",
    "WeeklyMetrics",
    "OFFER_TYPES",
    "ACTION_VERBS",
    "USER_RESPONSES",
    "HOLD_REASONS",
    "RITUALS",
]
