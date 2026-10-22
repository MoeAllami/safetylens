# Progress

**Current phase:** 1 — Ingest
**Branch:** phase-1-ingest

## Done (2026-10-21)
- uv package (Python 3.12), typer + dev deps (ruff, mypy, pytest, pytest-cov, pre-commit, respx)
- Makefile (stubs for later phases), pytest markers, ruff/mypy/coverage config
- .gitignore, .gitattributes, .env.example, pre-commit, GitHub Actions CI
- `make check` exit 0 (2 passed, 1 xfailed, coverage 100%); CI green on PR #1 (merged)

## Phase 1 — Ingest (branch `phase-1-ingest`, in progress)
Done: layouts verified against docs/data/CMPL.txt and RCL.txt (recalls have 29 fields, no PII);
download (ETag / Last-Modified, atomic), position-based parser (drops PII), Parquet, DuckDB
`complaints_raw` / `recalls_raw` / `ingest_runs`, `safetylens ingest|dq`, 23 tests; `make check` exit 0;
`pytest tests/ingest -m idempotent` exit 0.

## Next up
1. Owner OKs the real download; run `make data-dev` then `make dq`; record row counts below
2. If real data has duplicate (odino, component) or missing ODINO: stop and ask how to handle it
3. Optional: 2,000-row real-sample fixture in tests/fixtures (owner must unlock protected files; PII blanked)
4. `/phase-check 1`, open PR, then `/learn`

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
| 1 Ingest | in progress | – | – |
| 2 Analytics | not started | – | – |
| 3 Search | not started | – | – |
| 4 Answers | not started | – | – |
| 5 Web app | not started | – | – |
| 6 Polish | not started | – | – |

## Blockers / decisions needed
- OS decided: native Windows with Git Bash; uv, make, jq, gh installed via winget (restart the terminal so PATH picks them up)
- Confirm LLM choice (default: Anthropic API, Haiku planner + Sonnet writer)
