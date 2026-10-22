---
name: verify
description: Run the SafetyLens code-health checks (ruff, format, mypy strict, pytest with coverage) and report the result. Use before every commit and whenever asked whether the code is in a good state.
---

Run, from the repo root:

```
make check
```

Then report:
- The exit code.
- If it failed: each failing tool, the first error per file, and your proposed fix.
- If it passed: one line with test count and coverage percent.

Rules:
- Never change test expectations, coverage thresholds, ruff or mypy config to make this pass.
- If `make check` does not exist yet (early Phase 0), run `uv run ruff check . && uv run pytest -q`
  and say that the Makefile target is still missing.
