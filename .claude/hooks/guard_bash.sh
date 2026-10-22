#!/usr/bin/env bash
# PreToolUse (Bash): block commands that bypass the project's rules.
set -uo pipefail
INPUT=$(cat)
CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
[ -z "$CMD" ] && exit 0

block() { echo "Blocked: $1" >&2; exit 2; }

if printf '%s' "$CMD" | grep -Eq '(^|[;&|[:space:]])(uv[[:space:]]+)?pip3?[[:space:]]+install'; then
  block "use 'uv add <package>' (or 'uv add --dev') instead of pip install."
fi
if printf '%s' "$CMD" | grep -Eq 'rm[[:space:]]+-[a-zA-Z]*r[a-zA-Z]*f?[a-zA-Z]*[[:space:]]+[^;&|]*(\b|/)(data|src|tests|evals|\.git)(/|[[:space:]]|$)'; then
  block "recursive delete of data/, src/, tests/, evals/ or .git is not allowed. Ask the owner."
fi
if printf '%s' "$CMD" | grep -Eq 'git[[:space:]]+push([[:space:]].*)?[[:space:]](--force|-f)([[:space:]=]|$)'; then
  block "force-push is not allowed."
fi
if printf '%s' "$CMD" | grep -Eq -- '--no-verify'; then
  block "--no-verify skips the checks; fix the failure instead."
fi
if printf '%s' "$CMD" | grep -Eq '\.unlock-protected'; then
  block "only the owner may create or remove the unlock file."
fi
if printf '%s' "$CMD" | grep -Eq '(cat|less|more|head|tail|grep|sed|awk)[[:space:]]+([^;&|]*[[:space:]/])?\.env([[:space:];&|]|$)'; then
  block ".env holds secrets; read settings through pydantic-settings instead."
fi
exit 0
