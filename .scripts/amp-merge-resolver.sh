#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: .scripts/amp-merge-resolver.sh [conflicted-file ...]

Guided CLI fallback for Amp update conflicts when AskUserQuestion is not available.
Run from the vault repository root during a failed `git merge`.
USAGE
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
fi

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "Error: run this from inside the Amp git repository." >&2
  exit 1
fi

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

if [ "$#" -gt 0 ]; then
  files=("$@")
else
  mapfile -t files < <(git diff --name-only --diff-filter=U)
fi

if [ "${#files[@]}" -eq 0 ]; then
  echo "No unresolved merge conflicts found."
  exit 0
fi

show_context() {
  local file="$1"
  echo
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "Conflict: $file"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo
  echo "Status:"
  git status --short -- "$file" || true
  echo
  echo "Conflict preview, first 180 lines:"
  if git diff --cc -- "$file" >/dev/null 2>&1; then
    git diff --cc -- "$file" | sed -n '1,180p'
  elif [ -f "$file" ]; then
    sed -n '1,180p' "$file"
  else
    echo "No text preview available."
  fi
  echo
}

safe_copy_path() {
  local file="$1"
  local suffix="$2"
  local candidate="${file}${suffix}"
  local n=1
  while [ -e "$candidate" ]; do
    candidate="${file}${suffix}.${n}"
    n=$((n + 1))
  done
  printf '%s\n' "$candidate"
}

keep_mine() {
  local file="$1"
  git checkout --ours -- "$file"
  git add -- "$file"
  echo "✓ Kept your version: $file"
}

use_amp() {
  local file="$1"
  git checkout --theirs -- "$file"
  git add -- "$file"
  echo "✓ Used Amp update version: $file"
}

is_protected_user_file() {
  local file="$1"
  case "$file" in
    00-Inbox/*|01-Quarter_Goals/*|02-Week_Priorities/*|03-Tasks/*|04-Projects/*|05-Areas/*|06-Resources/*|07-Archives/*)
      return 0
      ;;
    System/user-profile.yaml|System/pillars.yaml|.env|.mcp.json)
      return 0
      ;;
    .claude/skills/*-custom|.claude/skills/*-custom/*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

keep_both() {
  local file="$1"
  local amp_copy
  amp_copy="$(safe_copy_path "$file" ".amp-update")"
  mkdir -p "$(dirname "$amp_copy")"
  if ! git show ":3:$file" > "$amp_copy" 2>/dev/null; then
    echo "Could not extract Amp version for $file. Leaving unresolved." >&2
    return 1
  fi
  git checkout --ours -- "$file"
  git add -- "$file" "$amp_copy"
  echo "✓ Kept your version at $file"
  echo "✓ Saved Amp update version at $amp_copy"
}

instructions() {
  local file="$1"
  local note_file="System/update-conflict-instructions.md"
  mkdir -p "$(dirname "$note_file")"
  echo "Type your instructions for resolving $file, then press Enter."
  read -r note || note=""
  {
    echo "## $file"
    echo
    echo "$(date '+%Y-%m-%d %H:%M:%S')"
    echo
    echo "$note"
    echo
  } >> "$note_file"
  echo "✓ Saved instructions to $note_file"
  echo "Conflict left unresolved so Amp can apply those instructions."
}

prompt_choice() {
  local file="$1"
  local choice=""
  local attempts=0
  while [ "$attempts" -lt 2 ]; do
    cat <<'PROMPT'
Choose how to resolve this file:
  1) Keep mine     - preserves your local version, skips Amp changes for this file
  2) Use Amp       - takes the update version, discards your local edits for this file
  3) Keep both     - keeps your file and saves the Amp version as <file>.amp-update
  4) Instructions  - write instructions and leave this conflict for Amp/manual follow-up
PROMPT
    printf 'Choice [1-4]: '
    read -r choice || choice=""
    case "$choice" in
      1) keep_mine "$file"; return 0 ;;
      2) use_amp "$file"; return 0 ;;
      3) keep_both "$file"; return 0 ;;
      4) instructions "$file"; return 0 ;;
      *) echo "Invalid choice." ;;
    esac
    attempts=$((attempts + 1))
  done
  if is_protected_user_file "$file"; then
    echo "Defaulting to: Keep mine, because this is user-owned content."
    keep_mine "$file"
  else
    echo "Defaulting to: Use Amp."
    use_amp "$file"
  fi
}

for file in "${files[@]}"; do
  if ! git diff --name-only --diff-filter=U -- "$file" | grep -qxF "$file"; then
    echo "Skipping $file, not currently conflicted."
    continue
  fi
  show_context "$file"
  prompt_choice "$file"
  echo
done

remaining="$(git diff --name-only --diff-filter=U)"
if [ -n "$remaining" ]; then
  echo "Remaining unresolved conflicts:"
  echo "$remaining"
  exit 2
fi

echo "All selected conflicts are resolved. Review with git diff --cached, then commit."
