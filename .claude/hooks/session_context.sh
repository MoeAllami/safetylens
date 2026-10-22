#!/usr/bin/env bash
# SessionStart (startup|resume|compact): re-inject where the project stands.
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
echo "SafetyLens session context"
BRANCH=$(git branch --show-current 2>/dev/null) && [ -n "$BRANCH" ] && echo "Git branch: $BRANCH"
if [ -f docs/PROGRESS.md ]; then
  echo "--- docs/PROGRESS.md (top) ---"
  head -n 40 docs/PROGRESS.md
  echo "--- end ---"
else
  echo "docs/PROGRESS.md not found: create it from the starter kit before continuing."
fi
echo "Rules: numbers from SQL, words from records; COUNT(DISTINCT odino); no PII; never weaken checks."
exit 0
