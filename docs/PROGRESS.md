# Progress

**Current phase:** 2 — Normalize + analytics
**Branch:** phase-2-analytics

## Done (2026-10-21)
- uv package (Python 3.12), typer + dev deps (ruff, mypy, pytest, pytest-cov, pre-commit, respx)
- Makefile (stubs for later phases), pytest markers, ruff/mypy/coverage config
- .gitignore, .gitattributes, .env.example, pre-commit, GitHub Actions CI
- `make check` exit 0 (2 passed, 1 xfailed, coverage 100%); CI green on PR #1 (merged)

## Phase 2 — Normalize + analytics (branch `phase-2-analytics`)
Done (2026-10-22): `safetylens build` (complaints, complaint_docs, recalls, component_systems,
vehicle_models, model_aliases; one transaction); templates complaint_count, top_components,
monthly_trend (zero-filled in SQL), severity (per complaint), recalls_by_vehicle; golden tests with
hand-computed expectations + plain-Python oracle on the real fixture; `make crosscheck` with
`evals/crosscheck_vehicles.yaml` (owner-approved list). Gate: `make check` exit 0 (50 passed, 94%),
`make dq` exit 0, `make crosscheck` 10/10 exact (0.00% diff).
Findings: the API only answers to its own model names (`MODEL Y (All Variants)`), so crosscheck
queries every API name starting with our model and filters on the returned productModel; API
results include VIN and narrative, so only ODI numbers are cached.

## Phase 1 — Ingest (merged, PR #2)
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
1. Owner removes the protected-files unlock; `/phase-check 2`; push `phase-2-analytics`, PR, CI green, `/learn`
2. Phase 3: DuckDB fts BM25 index over `complaint_docs.narrative`, filtered by vehicle/component
3. Phase 3: bge-small-en-v1.5 embeddings (batched, resumable) + hybrid reciprocal rank fusion, `safetylens search`
4. Phase 3: draft 60 labeled queries for `evals/retrieval_labels.yaml` (owner verifies), `make eval-retrieval`

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
| 2 Analytics | gates pass; /phase-check pending | make check, make dq exit 0; crosscheck 10/10 exact | 2026-10-22 |
| 3 Search | not started | – | – |
| 4 Answers | not started | – | – |
| 5 Web app | not started | – | – |
| 6 Polish | not started | – | – |

## Blockers / decisions needed
- OS decided: native Windows with Git Bash; uv, make, jq, gh installed via winget (restart the terminal so PATH picks them up)
- Confirm LLM choice (default: Anthropic API, Haiku planner + Sonnet writer)
