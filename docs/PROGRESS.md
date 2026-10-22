# Progress

**Current phase:** 0 — Scaffold and guardrails
**Branch:** phase-0-scaffold

## Done (2026-10-21)
- uv package (Python 3.12), typer + dev deps (ruff, mypy, pytest, pytest-cov, pre-commit, respx)
- Makefile (stubs for later phases), pytest markers, ruff/mypy/coverage config
- .gitignore, .gitattributes, .env.example, pre-commit, GitHub Actions CI
- `make check` exit 0 (2 passed, 1 xfailed, coverage 100%); CI green on PR #1 (merged)

## Next up (Phase 1 — Ingest, branch `phase-1-ingest`; start in plan mode)
1. Confirm `/hooks` lists the project hooks (last open Phase 0 gate item)
2. Download step: NHTSA flat files with checksum + If-Modified-Since (load `nhtsa-data` skill first)
3. Parse by position (49 or 51 fields), drop PII columns at ingest, write Parquet
Then: DuckDB `complaints_raw`, `recalls_raw`, `ingest_runs`; 2,000-row fixture (ask owner first); `make dq`.

## Non-blocking review notes
- Makefile `check` duplicates `lint`/`typecheck` recipes; could be `check: lint typecheck` + pytest
- pre-commit ruff rev v0.8.6 is older than pinned ruff>=0.17.1; bump the rev to avoid format drift

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
| 0 Scaffold | done pending /hooks check | make check exit 0; CI green | 2026-10-21 |
| 1 Ingest | not started | – | – |
| 2 Analytics | not started | – | – |
| 3 Search | not started | – | – |
| 4 Answers | not started | – | – |
| 5 Web app | not started | – | – |
| 6 Polish | not started | – | – |

## Blockers / decisions needed
- OS decided: native Windows with Git Bash; uv, make, jq, gh installed via winget (restart the terminal so PATH picks them up)
- Confirm LLM choice (default: Anthropic API, Haiku planner + Sonnet writer)
