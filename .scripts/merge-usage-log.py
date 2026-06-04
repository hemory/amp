#!/usr/bin/env python3
"""Merge Amp usage-log templates without losing user checkmarks.

The helper is intentionally conservative: it reads a new template and an
existing user-owned usage log, then emits a merged file that keeps checked
state and consent answers while adding new template entries. Use --dry-run to
inspect the result before writing.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

CHECKBOX_RE = re.compile(
    r"^(?P<prefix>\s*- \[)(?P<mark>[ xX])(?P<suffix>\]\s+)"
    r"(?P<label>.+?)(?P<trailing>\s*)$"
)
CONSENT_RE = re.compile(
    r"^(?P<prefix>\s*-\s+Consent (?:asked|decision):\s*)"
    r"(?P<value>.+?)(?P<trailing>\s*)$"
)


@dataclass(frozen=True)
class ParsedLog:
    checked: dict[str, str]
    consent: dict[str, str]
    entries: dict[str, str]


def normalize_label(label: str) -> str:
    """Normalize a checkbox label so command text or spacing changes still match."""
    without_command = re.sub(r"`[^`]+`", "", label)
    without_markup = re.sub(r"[*_]+", "", without_command)
    return re.sub(r"\s+", " ", without_markup).strip().casefold()


def parse_log(text: str) -> ParsedLog:
    checked: dict[str, str] = {}
    consent: dict[str, str] = {}
    entries: dict[str, str] = {}

    for line in text.splitlines():
        checkbox = CHECKBOX_RE.match(line)
        if checkbox:
            label = checkbox.group("label").strip()
            key = normalize_label(label)
            entries[key] = line
            if checkbox.group("mark").lower() == "x":
                checked[key] = "x"
            continue

        consent_match = CONSENT_RE.match(line)
        if consent_match:
            field = line.split(":", 1)[0].strip().casefold()
            consent[field] = consent_match.group("value").strip()

    return ParsedLog(checked=checked, consent=consent, entries=entries)


def merge_usage_log(template_text: str, existing_text: str) -> str:
    template = parse_log(template_text)
    existing = parse_log(existing_text)
    emitted_keys: set[str] = set()
    merged_lines: list[str] = []

    for line in template_text.splitlines():
        checkbox = CHECKBOX_RE.match(line)
        if checkbox:
            label = checkbox.group("label").strip()
            key = normalize_label(label)
            mark = "x" if key in existing.checked or key in template.checked else " "
            emitted_keys.add(key)
            merged_lines.append(
                f"{checkbox.group('prefix')}{mark}{checkbox.group('suffix')}"
                f"{checkbox.group('label')}{checkbox.group('trailing')}"
            )
            continue

        consent_match = CONSENT_RE.match(line)
        if consent_match:
            field = line.split(":", 1)[0].strip().casefold()
            value = existing.consent.get(field, consent_match.group("value").strip())
            merged_lines.append(
                f"{consent_match.group('prefix')}{value}{consent_match.group('trailing')}"
            )
            continue

        merged_lines.append(line)

    legacy_lines = [
        line for key, line in existing.entries.items() if key not in emitted_keys
    ]
    if legacy_lines:
        if merged_lines and merged_lines[-1].strip():
            merged_lines.append("")
        merged_lines.extend([
            "## Legacy or Removed Features",
            "",
            "These entries were present in your existing usage log but are not in the "
            "current template. They are preserved for auditability and may be "
            "deleted manually if no longer useful.",
            "",
            *legacy_lines,
        ])

    return "\n".join(merged_lines).rstrip() + "\n"


def read_optional(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def self_test() -> None:
    template = """# Amp Feature Usage

## Analytics Consent
- Consent asked: false
- Consent decision: pending

## Core Features
- [ ] Daily Plan (`/daily-plan`)
- [ ] New Feature (`/new-feature`)
"""
    existing = """# Amp Feature Usage

## Analytics Consent
- Consent asked: true
- Consent decision: accepted

## Core Features
- [x] Daily Plan (`/daily-plan`)
- [x] Old Feature (`/old-feature`)
"""
    merged = merge_usage_log(template, existing)
    assert "- Consent asked: true" in merged
    assert "- Consent decision: accepted" in merged
    assert "- [x] Daily Plan (`/daily-plan`)" in merged
    assert "- [ ] New Feature (`/new-feature`)" in merged
    assert "## Legacy or Removed Features" in merged
    assert "- [x] Old Feature (`/old-feature`)" in merged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Merge Amp usage-log templates while preserving user state."
    )
    parser.add_argument(
        "--source",
        default="System/Templates/usage_log.md",
        help="new usage log template",
    )
    parser.add_argument(
        "--target",
        default="System/usage_log.md",
        help="existing user-owned usage log",
    )
    parser.add_argument("--output", help="write merged output here; defaults to --target")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print merged output to stdout without writing",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if target would change; implies no write",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="print a unified diff instead of the full merged file in dry-run/check mode",
    )
    parser.add_argument("--self-test", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.self_test:
        self_test()
        print("merge-usage-log self-test OK")
        return 0

    source = Path(args.source)
    target = Path(args.target)
    output = Path(args.output) if args.output else target

    if not source.exists():
        parser.error(f"source template not found: {source}")

    template_text = source.read_text(encoding="utf-8")
    existing_text = read_optional(target)
    merged = merge_usage_log(template_text, existing_text)

    if args.check or args.dry_run:
        if args.diff:
            diff = difflib.unified_diff(
                existing_text.splitlines(keepends=True),
                merged.splitlines(keepends=True),
                fromfile=str(target),
                tofile=str(source),
            )
            sys.stdout.writelines(diff)
        else:
            sys.stdout.write(merged)
        if args.check and existing_text != merged:
            return 1
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(merged, encoding="utf-8")
    print(f"Merged usage log written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
