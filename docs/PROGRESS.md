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
- No more per-phase `TODO(you)` stubs: owner removed the rule from CLAUDE.md and asked for the Phase 0
  stub (`is_valid_odino`) to be implemented (commit ffcd220).

`/phase-check 1` (2026-10-21): all three gate commands exit 0; reviewer's blocking fixture item is now done:
`tests/fixtures/complaints_sample.txt` (2,000 rows, 1,380 complaints, PII fields blanked) and
`recalls_sample.txt` (200 rows), built by `scripts/make_fixtures.py`, read by `tests/ingest/test_real_sample.py`.

## Next up
1. Owner removes the protected-files unlock; push `phase-1-ingest`, open PR, CI green, `/learn`
2. Phase 2: `complaints` (one row per odino x component, prod_type V, MILES/VEH_SPEED 0 -> NULL,
   YEARTXT 9999 -> NULL) and `complaint_docs` (one row per odino)
3. Phase 2: `component_system` + model alias table (rapidfuzz, checked against the models API)
4. Phase 2: SQL templates (top components, monthly trend, severity, recalls by vehicle) + `make crosscheck`

## Non-blocking review notes
- Makefile `check` duplicates `lint`/`typecheck` recipes; could be `check: lint typecheck` + pytest
- pre-commit ruff rev v0.8.6 is older than pinned ruff>=0.17.1; bump the rev to avoid format drift
- Phase 1 review: parquet stats sidecar is not written atomically and bad JSON is not a cache miss (pipeline.py)
- Phase 1 review: cache-invalidation branch untested; idempotency test never exercises the 304 path
- Phase 1 review: on 304 the zip on disk is not re-checked against the stored sha/size (download.py)
- Phase 1 review: loads + ingest_runs are not one transaction; connection leaks on error (pipeline.py, cli.py)
- Phase 1 review: use `con.begin()/commit()/rollback()`; pass REQUIRED_TABLES as a parameter to dq_tables_present.sql
- Phase 1 review: report rows_rejected / rows_cp1252 from the latest ingest_runs in `make dq` (INFO or threshold)

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
| 0 Scaffold | done (owner confirmed /hooks) | make check exit 0; CI green | 2026-10-21 |
| 1 Ingest | done | make check, make dq, pytest -m idempotent exit 0; fixture committed | 2026-10-21 |
| 2 Analytics | not started | – | – |
| 3 Search | not started | – | – |
| 4 Answers | not started | – | – |
| 5 Web app | not started | – | – |
| 6 Polish | not started | – | – |

## Blockers / decisions needed
- OS decided: native Windows with Git Bash; uv, make, jq, gh installed via winget (restart the terminal so PATH picks them up)
- Confirm LLM choice (default: Anthropic API, Haiku planner + Sonnet writer)
