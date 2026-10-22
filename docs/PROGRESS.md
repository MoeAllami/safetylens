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
`complaints_raw` / `recalls_raw` / `ingest_runs`, `safetylens ingest|dq`, 25 tests.
Real dev slice ingested (40 s). Gate commands all exit 0: `make check`, `make dq`,
`pytest tests/ingest -m idempotent`; two real re-runs gave identical row counts and checksums.
Owner decisions (2026-10-21):
- D3 duplicate check is scoped to vehicle rows (prod_type V). One ODINO can name a vehicle plus a
  tire/equipment/child seat under the same component (5,048 such pairs). 63 non-vehicle repeat groups are
  reported as INFO. PLAN.md D3 and nhtsa-data gotcha 9 updated.
- Files are UTF-8, not cp1252: decode UTF-8 per line with a cp1252 fallback (0 fallbacks in the dev slice;
  cp1252 had produced mojibake on ~47k lines). Skill gotcha 5 updated.

## Next up
1. `/phase-check 1`, push `phase-1-ingest`, open PR, CI green, then `/learn`
2. Optional: 2,000-row real-sample fixture in tests/fixtures (owner must unlock protected files; PII blanked)
3. Phase 2: normalize `complaints` / `complaint_docs`, `component_system`, model alias table, SQL templates

## Non-blocking review notes
- Makefile `check` duplicates `lint`/`typecheck` recipes; could be `check: lint typecheck` + pytest
- pre-commit ruff rev v0.8.6 is older than pinned ruff>=0.17.1; bump the rev to avoid format drift

## Measured numbers
| Metric | Value | Date |
|---|---|---|
| Complaint rows (dev slice) | 625,137 | 2026-10-21 |
| Distinct ODI (dev slice) | 430,187 | 2026-10-21 |
| Recall rows / distinct campaigns (post-2010) | 246,253 / 15,332 | 2026-10-21 |
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
