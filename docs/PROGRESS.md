# Progress

**Current phase:** 0 — Scaffold and guardrails
**Branch:** phase-0-scaffold

## Done (2026-10-21)
- uv package (Python 3.12), typer + dev deps (ruff, mypy, pytest, pytest-cov, pre-commit, respx)
- Makefile (stubs for later phases), pytest markers, ruff/mypy/coverage config
- .gitignore, .gitattributes, .env.example, pre-commit, GitHub Actions CI
- `make check` exit 0 locally (2 passed, 1 xfailed, coverage 100%)

## Next up
1. Commit, push `phase-0-scaffold`, open PR; confirm CI green
2. Confirm `/hooks` lists the project hooks; run `/phase-check 0`
3. Implement `is_valid_odino`, then remove its xfail marker; then run `/learn`

## TODO(you) stubs open
- `src/safetylens/validate.py::is_valid_odino` — test is `xfail(strict=True)` in tests/test_smoke.py; remove the marker once it passes

## Measured numbers
| Metric | Value | Date |
|---|---|---|
| Complaint rows (dev slice) | – | – |
| Distinct ODI (dev slice) | – | – |
| Embedding throughput (docs/s) | – | – |
| Hybrid recall@10 | – | – |
| Golden pass rate | – | – |
| p95 latency | – | – |
| Mean cost / question | – | – |

## Phase log
| Phase | Status | Gate result | Date |
|---|---|---|---|
| 0 Scaffold | in progress | – | – |
| 1 Ingest | not started | – | – |
| 2 Analytics | not started | – | – |
| 3 Search | not started | – | – |
| 4 Answers | not started | – | – |
| 5 Web app | not started | – | – |
| 6 Polish | not started | – | – |

## Blockers / decisions needed
- OS decided: native Windows with Git Bash; uv, make, jq, gh installed via winget (restart the terminal so PATH picks them up)
- Confirm LLM choice (default: Anthropic API, Haiku planner + Sonnet writer)
