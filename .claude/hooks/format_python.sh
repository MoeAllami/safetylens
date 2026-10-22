#!/usr/bin/env bash
# PostToolUse (Edit|Write): format and auto-fix the edited Python file. Never blocks.
# F401 (unused import) is not auto-fixed, so an import added before its first use survives.
set -uo pipefail
INPUT=$(cat)
FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')
case "$FILE_PATH" in *.py) ;; *) exit 0 ;; esac
[ -f "$FILE_PATH" ] || exit 0
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
command -v uv >/dev/null 2>&1 || exit 0
[ -f pyproject.toml ] || exit 0
uv run --quiet ruff format "$FILE_PATH" >/dev/null 2>&1 || true
uv run --quiet ruff check --fix --unfixable F401 "$FILE_PATH" >/dev/null 2>&1 || true
exit 0
