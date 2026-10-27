#!/bin/bash
# Appends each due follow-up to the in-flight file the overnight check reads, once per distinct line.
here="$(cd "$(dirname "$0")" && pwd)"
target="${IN_FLIGHT_FILE:-/home/deploy/.claude/projects/-home-deploy-workspace-small-house/memory/in-flight-2026-10-25.md}"
output="$(python3 "$here/due_followups.py" "$@")"
status=$?
[ "$status" -eq 1 ] || exit "$status"
printf '%s\n' "$output" | while IFS= read -r line; do
  grep -qxF -- "- $line" "$target" || printf -- '- %s\n' "$line" >> "$target"
done
