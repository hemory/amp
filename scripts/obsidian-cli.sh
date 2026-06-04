#!/usr/bin/env bash
# obsidian-cli.sh — Centralized Obsidian CLI wrapper for Amp
#
# Usage:
#   source scripts/obsidian-cli.sh
#   obs open "My Note" [newtab]
#   obs search "query" [path] [limit] [format]
#   obs read "My Note"
#   obs create "name" "content" [template] [open]
  #   obs append "My Note" "content"
  #   obs prepend "My Note" "content"
  #   obs property:get "My Note" "property_name"
  #   obs property:set "My Note" "property_name" "value" [type]
  #   obs backlinks "My Note" [format]
  #   obs tasks [todo|done] [limit] [format]
  #   obs tags [counts] [sort]
  #   obs daily [read|append|prepend|path] [content]
  #   obs search:context "query" [path] [limit]
  #   obs orphans [total]
  #   obs unresolved [total|verbose]
  #   obs deadends [total]
  #   obs vault [info_type]

# Note: Do not enable 'set -euo pipefail' globally here; this file is meant to be sourced.

# Binary detection
OBS_BIN=""
_obs_find_binary() {
  local candidates=(
    "/Applications/Obsidian.app/Contents/MacOS/obsidian"
    "/usr/local/bin/obsidian"
    "$HOME/bin/obsidian"
  )
  for bin in "${candidates[@]}"; do
    if [[ -x "$bin" ]]; then
      OBS_BIN="$bin"
      return 0
    fi
  done
  # Try PATH
  if command -v obsidian &>/dev/null; then
    OBS_BIN="$(command -v obsidian)"
    return 0
  fi
  echo "Error: Obsidian CLI not found" >&2
  return 1
}

# Core execution: runs CLI command and strips noise
_obs_exec() {
  if [[ -z "$OBS_BIN" ]]; then
    _obs_find_binary || return 1
  fi
  "$OBS_BIN" "$@" 2>&1 | sed \
    '/Loading updated app package/d' \
    '/installer is out of date/d' \
    '/better CLI support/d'
}

# Open a file in Obsidian (by name, like wikilinks)
obs_open() {
  local file="${1:?Usage: obs_open <file> [newtab]}"
  local newtab="${2:-newtab}"
  if [[ "$newtab" == "newtab" ]]; then
    _obs_exec open file="$file" newtab
  else
    _obs_exec open file="$file"
  fi
}

# Search vault contents
obs_search() {
  local query="${1:?Usage: obs_search <query> [path] [limit] [format]}"
  local path="${2:-}"
  local limit="${3:-}"
  local format="${4:-text}"
  local args=(search query="$query")
  [[ -n "$path" ]] && args+=(path="$path")
  [[ -n "$limit" ]] && args+=(limit="$limit")
  [[ "$format" != "text" ]] && args+=(format="$format")
  _obs_exec "${args[@]}"
}

# Search with line context
obs_search_context() {
  local query="${1:?Usage: obs_search_context <query> [path] [limit]}"
  local path="${2:-}"
  local limit="${3:-}"
  local args=(search:context query="$query")
  [[ -n "$path" ]] && args+=(path="$path")
  [[ -n "$limit" ]] && args+=(limit="$limit")
  _obs_exec "${args[@]}"
}

# Read file contents
obs_read() {
  local file="${1:?Usage: obs_read <file>}"
  _obs_exec read file="$file"
}

# Create a new file
obs_create() {
  local name="${1:?Usage: obs_create <name> [content] [template] [open]}"
  local content="${2:-}"
  local template="${3:-}"
  local should_open="${4:-open}"
  local args=(create name="$name")
  [[ -n "$content" ]] && args+=(content="$content")
  [[ -n "$template" ]] && args+=(template="$template")
  [[ "$should_open" == "open" ]] && args+=(open newtab)
  _obs_exec "${args[@]}"
}

# Append content to a file
obs_append() {
  local file="${1:?Usage: obs_append <file> <content>}"
  local content="${2:?Usage: obs_append <file> <content>}"
  _obs_exec append file="$file" content="$content"
}

# Prepend content to a file
obs_prepend() {
  local file="${1:?Usage: obs_prepend <file> <content>}"
  local content="${2:?Usage: obs_prepend <file> <content>}"
  _obs_exec prepend file="$file" content="$content"
}

# Read a property from a file
obs_property_get() {
  local file="${1:?Usage: obs_property_get <file> <property>}"
  local name="${2:?Usage: obs_property_get <file> <property>}"
  _obs_exec property:get name="$name" file="$file"
}

# Set a property on a file
obs_property_set() {
  local file="${1:?Usage: obs_property_set <file> <property> <value> [type]}"
  local name="${2:?Usage: obs_property_set <file> <property> <value> [type]}"
  local value="${3:?Usage: obs_property_set <file> <property> <value> [type]}"
  local type="${4:-}"
  local args=(property:set name="$name" value="$value" file="$file")
  [[ -n "$type" ]] && args+=(type="$type")
  _obs_exec "${args[@]}"
}

# Remove a property from a file
obs_property_remove() {
  local file="${1:?Usage: obs_property_remove <file> <property>}"
  local name="${2:?Usage: obs_property_remove <file> <property>}"
  _obs_exec property:remove name="$name" file="$file"
}

# List backlinks to a file
obs_backlinks() {
  local file="${1:?Usage: obs_backlinks <file> [format]}"
  local format="${2:-tsv}"
  _obs_exec backlinks file="$file" format="$format"
}

# List tasks
obs_tasks() {
  local filter="${1:-todo}"  # todo, done, or empty for all
  local limit="${2:-}"
  local format="${3:-text}"
  local args=(tasks)
  [[ "$filter" == "todo" ]] && args+=(todo)
  [[ "$filter" == "done" ]] && args+=(done)
  [[ -n "$limit" ]] && args+=(limit="$limit")
  [[ "$format" != "text" ]] && args+=(format="$format")
  _obs_exec "${args[@]}"
}

# List tags
obs_tags() {
  local counts="${1:-}"
  local sort="${2:-}"
  local args=(tags)
  [[ "$counts" == "counts" ]] && args+=(counts)
  [[ -n "$sort" ]] && args+=(sort="$sort")
  _obs_exec "${args[@]}"
}

# Daily note operations
obs_daily() {
  local action="${1:-path}"  # path, read, append, prepend, open
  local content="${2:-}"
  case "$action" in
    path)    _obs_exec daily:path ;;
    read)    _obs_exec daily:read ;;
    open)    _obs_exec daily ;;
    append)
      [[ -z "$content" ]] && { echo "Error: content required for append" >&2; return 1; }
      _obs_exec daily:append content="$content"
      ;;
    prepend)
      [[ -z "$content" ]] && { echo "Error: content required for prepend" >&2; return 1; }
      _obs_exec daily:prepend content="$content"
      ;;
    *)
      echo "Error: unknown obs_daily action: '$action'" >&2
      echo "Usage: obs_daily [path|read|append|prepend|open] [content]" >&2
      return 1
      ;;
  esac
}

# Vault health: orphans
obs_orphans() {
  local total="${1:-}"
  if [[ "$total" == "total" ]]; then
    _obs_exec orphans total
  else
    _obs_exec orphans
  fi
}

# Vault health: unresolved links
obs_unresolved() {
  local mode="${1:-total}"  # total, verbose, or counts
  local args=(unresolved)
  case "$mode" in
    total)   args+=(total) ;;
    verbose) args+=(verbose) ;;
    counts)  args+=(counts) ;;
  esac
  _obs_exec "${args[@]}"
}

# Vault health: deadends (no outgoing links)
obs_deadends() {
  local total="${1:-}"
  if [[ "$total" == "total" ]]; then
    _obs_exec deadends total
  else
    _obs_exec deadends
  fi
}

# Vault info
obs_vault() {
  local info="${1:-}"
  if [[ -n "$info" ]]; then
    _obs_exec vault info="$info"
  else
    _obs_exec vault
  fi
}

# Move/rename a file
obs_move() {
  local file="${1:?Usage: obs_move <file> <destination>}"
  local to="${2:?Usage: obs_move <file> <destination>}"
  _obs_exec move file="$file" to="$to"
}

# File info
obs_file_info() {
  local file="${1:?Usage: obs_file_info <file>}"
  _obs_exec file file="$file"
}

# List outgoing links
obs_links() {
  local file="${1:?Usage: obs_links <file>}"
  _obs_exec links file="$file"
}

# Convenience: one-shot command passthrough
# Usage: obs <any obsidian cli command and args>
obs() {
  _obs_exec "$@"
}

# Initialize on source
_obs_find_binary 2>/dev/null || true
