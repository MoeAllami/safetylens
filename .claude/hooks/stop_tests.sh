#!/usr/bin/env bash
# Stop: if src/ or tests/ changed since the last green run, run the fast test suite.
# On failure, block the stop and hand the failure back to Claude.
set -uo pipefail
INPUT=$(cat)
# Loop guard: if this stop was already caused by this hook, let Claude stop.
if [ "$(printf '%s' "$INPUT" | jq -r '.stop_hook_active // false')" = "true" ]; then exit 0; fi

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
[ -f pyproject.toml ] || exit 0
command -v uv >/dev/null 2>&1 || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

CHANGES=$( { git diff HEAD -- src tests 2>/dev/null; git ls-files --others --exclude-standard -- src tests | xargs -r cat 2>/dev/null; } | sha256sum | cut -d' ' -f1)
EMPTY=$(printf '' | sha256sum | cut -d' ' -f1)
[ "$CHANGES" = "$EMPTY" ] && exit 0
STAMP=.claude/.last_green
[ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$CHANGES" ] && exit 0

OUT=$(uv run --quiet pytest -m "not slow and not network" -x -q 2>&1)
CODE=$?
# 5 = no tests collected (early Phase 0): treat as green
if [ $CODE -eq 0 ] || [ $CODE -eq 5 ]; then
  echo "$CHANGES" > "$STAMP"
  exit 0
fi
{
  echo "Fast tests are failing after your changes. Fix them before finishing (or explain why you can't):"
  printf '%s\n' "$OUT" | tail -n 40
} >&2
exit 2
