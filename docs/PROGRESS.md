# Progress

**Current phase:** 5 — Web app
**Branch:** phase-5-web

## Done (2026-10-21)
- uv package (Python 3.12), typer + dev deps (ruff, mypy, pytest, pytest-cov, pre-commit, respx)
- Makefile (stubs for later phases), pytest markers, ruff/mypy/coverage config
- .gitignore, .gitattributes, .env.example, pre-commit, GitHub Actions CI
- `make check` exit 0 (2 passed, 1 xfailed, coverage 100%); CI green on PR #1 (merged)

## Phase 4 — Answer engine + evals (branch `phase-4-answers`)
Done (2026-10-22): `safetylens ask` = planner (claude-haiku-5-5, structured output) -> resolver (aliases +
rapidfuzz, asks when unsure) -> per-intent SQL -> rerank retrieval (8 complaints) -> writer
(claude-sonnet-5-5, server-side refusal fallback) -> validator (numbers from SQL, citations from evidence and
DB) -> one retry -> deterministic template fallback. Budget caps checked before every call (ask $2/day,
eval $5/day; JSONL ledger without prompts). Golden set `evals/golden.yaml`: 40 items (34 + 6 out-of-scope),
facts from SQL via `scripts/golden_facts.py`, owner-reviewed. 125 tests (FakeLLM only), `make check` exit 0.
`make eval` (2026-10-22, second run, report in evals/reports): numbers_grounded 100%, citations_valid 100%,
citations_supportive 98% (197/200), golden pass 92% (37/40), refusals 6/6, first draft valid 82%,
p50 5.7 s / p95 13.0 s, mean cost $0.0125 per question (+ $0.41 judge per run) -> PASS. Failures: g04, g15,
g33 (one unsupported citation each). First run: 90%, g04 failed on intent (planner varies on that question).
Judge verdicts for the owner's spot-check: data/eval/judge-2026-10-22.md (git-ignored; 200 verdicts).
`/phase-check 4` (2026-10-22): FAIL. Gates exit 0 (make check 126 passed; make eval third run: D5 100%,
D6 100%, D7 99%, D9 95% (38/40), refusals 6/6, first draft 91%, p50 6.1 s / p95 11.7 s, $0.0117/question),
but the reviewer found 4 blocking issues; the first three mean the D5 validator is weaker than its 100% says:
1. dates are split into year/month/day, so any number 1-31 counts as grounded when a date is in the rows
2. number words ("two owners") and digit+unit tokens ("60mph", "3x") are never checked
3. the template fallback is not validated and includes the planner's free-text search_text
4. answer/golden.py is 323 lines (> 300)
Fixed (2026-10-22, commit after dc1ff2e): all 4, with tests (131 passed). `make eval` with the stricter validator:
D5 100%, D6 100%, D7 96%, D9 85% (34/40, exactly at the target), refusals 6/6, first draft valid 59%
(was 82-91%), 7 template fallbacks, p50 6.0 s / p95 11.4 s, $0.0151/question -> PASS, but at the edge.
Weak spot: a fallback without a component filter cites "Example reports: [a] [b] [c]" with no topic, and the
judge rejects those (g01 0/3). Eval spend today $4.60 of $5, so no further eval run today.
Follow-up (owner option 2, commit 31c6709): template example lines name each report's own components (from
the DB); the report lists first-draft validator errors. Re-run of the 6 failing items only: 4/6 now pass
(g01, g05, g13, g25); g04 still picks "examples"; g30 one unsupported citation. First-draft rejections are
almost all the number word "one" (also "twice", and "12" from "12-volt"): the writer ignores the digits-only
instruction. Owner decision: keep "one" strict (2026-10-22).
Full `make eval` after these changes: D5 100%, D6 100%, D7 98%, D9 90% (36/40), refusals 6/6, first draft
valid 50% (16 of the 20 rejected drafts used a number word, almost all "one"), 4 template fallbacks,
p50 6.9 s / p95 13.3 s, $0.0160/question (+ $0.38 judge) -> PASS. Failures: g13, g15 (writer, 1 unsupported
citation each), g31, g34 (compare fallbacks, 2/3 supported). Spot-check file: data/eval/judge-2026-10-22.md.
`/phase-check 4` re-run (2026-10-22): FAIL. Gates exit 0 (make check 132 passed; make eval D5 100%, D6 100%,
D7 98%, D9 90%, refusals 6/6, first draft 53%, p50 7.0 s / p95 13.9 s, $0.0155/question). Reviewer confirmed the
4 earlier fixes and found 2 new blocking items:
1. campaign ids without brackets ("recall 22V100000", "(22V100000)", "[22V1, 23V2]", lowercase) skip the citation
   check (rule 2) -> also match bare campaign ids in citations_in, with tests for each form
2. digit+unit tokens are counted in prose but ignored in SQL values, so real components like
   "ELECTRICAL SYSTEM:12V/24V/48V BATTERY:CABLES" make both the writer and the template fail ("error")
   -> allow digits from SQL values with or without a unit; template test with such a component
Fixed (commit 3cc5bdf, 140 tests): both, plus compare evidence interleaved across vehicles. `make eval`:
D5 100%, D6 100%, D7 99%, D9 92% (37/40), refusals 6/6, first draft 68%, 2 fallbacks,
p50 6.4 s / p95 10.3 s, $0.0140/question (+ $0.40 judge) -> PASS. Failures: g04 (planner picks examples),
g32, g34 (one unsupported citation each).

## Phase 3 — Search (branch `phase-3-search`; D8 miss accepted by owner)
Done (2026-10-22): DuckDB fts BM25 over `complaint_docs`; bge-small-en-v1.5 embeddings on GPU
(428,507 docs in 557 s, 769 docs/s; resumable by (odino, narrative sha, model)); dense search by
cosine within the vehicle filter; RRF hybrid; cross-encoder rerank (BAAI/bge-reranker-base) of the
fused top 20; `safetylens index|search|eval-retrieval`; 81 tests, `make check` exit 0.
Labels: 60 queries written before any results (`evals/retrieval_queries.yaml`, commit ef374ef);
pooled top 20 of bm25/dense/hybrid (2,071 candidates), every narrative judged by Claude; 4 queries had
no relevant complaint (q18, q36, q43, q45) and are skipped. Owner spot-checked 10 queries (2026-10-22,
"good for now"); labels committed to `evals/retrieval_labels.yaml` (778 relevant, 1,291 not relevant).
Owner decision: add a reranker; choose settings on dev queries (odd ids) only; gate on test (even ids).
Dev sweep: depth 20 = 0.775, 30 = 0.739, 50 = 0.683 (base); bge-reranker-v2-m3 depth 20 = 0.762.
Result (recall@10, test split, measured once): bm25 0.733, dense 0.720, hybrid 0.770, rerank 0.777.
Gate D8 needs >= 0.80 -> FAIL. All splits: bm25 0.687, dense 0.719, hybrid 0.746, rerank 0.776.
Owner decision (2026-10-22, option a): accept the miss for now, keep labels and threshold unchanged,
move to Phase 4 (planner component filter should tighten retrieval) and re-measure D8 in Phase 6.
Test split has been looked at once; further tuning must be decided on dev queries only.

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

## Phase 5 — Web app (branch `phase-5-web`)
Done (2026-10-22): FastAPI + Jinja2 + HTMX + Pico (`src/safetylens/web/`): `/`, `POST /ask` (HTMX partial, full page
without HTMX), `/complaint/{odi}`, `/recall/{campaign}`, `/vehicle/{make}/{model}/{year}`; Altair charts from SQL rows;
disclaimer + attribution on every page; model text escaped before citation links; htmx/pico/vega vendored in
`web/static` (no CDN). `safetylens serve` / `make serve` (127.0.0.1:8000, engine loaded once). `make e2e`: Playwright,
FakeLLM on a test DB, ask -> answer -> citation -> complaint page -> NHTSA link + recall -> vehicle page (2 passed).
SDK errors (529, rate limit, connection, out of credit) now become LLMError (round-3 note 2). Per-stage timings on every
answer and a "Where the time goes" table in the eval report; subset runs (`--ids`) write the judge review to
data/eval/subset/. `make check`: 167 passed, 94% coverage. Record pages on the dev DB: 0.02-0.10 s.
Latency work (10-item subset of slow items, same ids each run):
| change | first draft ok | p50 / p95 | golden (10) |
|---|---|---|---|
| baseline | 30% | 10.3 / 14.1 s | 70% |
| writer gets allowed_numbers; narrative campaign ids not citable | 50% | 8.2 / 12.3 s | 90% |
| + writer effort low (env only, not yet in .env) | 70% | 6.7 / 13.2 s | 100% |
| + <= 120 words, explicit "never the word one", max_tokens 2000 (effort low in .env) | 70% | 6.3 / 8.7 s | 90% |
Full `make eval` (40 items), 2026-10-22:
| run | first draft ok | p50 / p95 | D7 | golden | result |
|---|---|---|---|---|---|
| 120 words, Sonnet writer | 100% | 4.9 / 8.1 s | 98% | 90% | PASS (D12 miss by 0.1 s) |
| 100 words, at most 3 components | 88% | 4.8 / 10.1 s | 97% | 90% | PASS, slower: reverted |
| Haiku writer (env only) | 50% | 4.4 / 7.1 s | 87% | 68% | FAIL: rejected |
| 120 words, Sonnet (final, committed report) | 85% | 4.6 / 9.8 s | 98% | 90% (6/6) | PASS |
D12 decision (owner, 2026-10-22): accepted as a near-miss, like D8 in Phase 3. The tail is API response time
variance (writer_1 p95 5.8-7.1 s across identical runs) plus the occasional retry; p95 of 40 is set by 2 answers.
Cost per question fell from $0.0161 to $0.0121. Haiku is fast but its citations often don't support the sentence.

## Next up
1. Owner: `make serve`, try a question in the browser; spot-check judge verdicts in data/eval/judge-2026-10-22.md
2. Owner: `/phase-check 5` (gate: make check, make e2e; D12 recorded as accepted miss), then PR, `/learn`
3. Phase 6: answer cache keyed by normalized plan (also cuts repeat-question latency to ~0), error pages, Dockerfile,
   README + data card + eval table + demo GIF, `make acceptance` on a fresh clone

## Non-blocking review notes
- Phase 4 round 3: "2023,42" hides 42 (lookbehind skips digits after a comma/period); SDK errors (529, rate limit,
  connection) are not mapped to LLMError, so ask/eval crash; budget estimate uses the configured model's price but
  fallback may serve a pricier one; judge checks only the first sentence citing each ODI; ordinals not flagged
- Phase 4 re-review: ".5"/"1e5" slip the number regex; fraction words (third, quarter) not flagged; compare template cites only the first vehicle's reports; scripts/golden_facts.py is 463 lines
- Phase 4 review: always use fallbacks="default" instead of the FALLBACK_CAPABLE list; unknown fallback price should not crash after paying
- Phase 4 review: planner errors show the safety-refusal text and count as correct refusals; add an "error" status
- Phase 4 review: clarify text echoes planner make/model; BUDGET text claims numbers that aren't shown; only allow parsed received dates
- Phase 4 review: existing_ids() queried per citation; a judge exception aborts the whole eval
- Phase 4 review: golden facts use the same compute() code as the pipeline, so D9 can't catch compute/SQL bugs (only crosscheck can); report name answers-<date>.md vs PLAN's <date>.md
- Phase 4: p95 13.7 s (D12 needs < 8 s in Phase 5); retries (18% of questions) and reranker load dominate
- Phase 2 review: build rollback path and the `crosscheck` CLI command are untested
- Phase 2 review: dq_complaint_attrs_consistent omits fail_date, miles, veh_speed, state (also any_value'd)
- Phase 2 review: recalls_by_vehicle ignores received_from/to silently; document or reject
- Phase 2 review: VehicleFilter matches model_key only, not model_aliases (Phase 4 resolver will use aliases)
- Phase 2 review: API cache age uses time.time(), not an injected clock; stale-cache path untested
- Phase 2 review: add a dq check that consequence/remedy/manufacturer agree within a recall campaign
- Phase 2 review: Python `\s` vs DuckDB RE2 `\s` in model_key; covered by test_python_model_key_matches_sql
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
| complaints / complaint_docs (vehicle, dev slice) | 616,578 / 428,507 | 2026-10-22 |
| recalls (vehicle, campaign x vehicle x component) | 109,237 | 2026-10-22 |
| Crosscheck vs live API (10 vehicles) | 10/10, max diff 0.00% | 2026-10-22 |
| Embedding throughput (docs/s) | 769 (RTX 4060 Ti) | 2026-10-22 |
| Hybrid recall@10 (test split) | 0.770 hybrid / 0.777 reranked | 2026-10-22 |
| Golden pass rate | 92% (37/40), refusals 6/6 (strict validator) | 2026-10-22 |
| p95 latency | 9.8 s final run (8.1-10.1 s range; p50 4.6 s) | 2026-10-22 |
| Mean cost / question | $0.0121 (+ judge $0.39 per eval run) | 2026-10-22 |

## Phase log
| Phase | Status | Gate result | Date |
|---|---|---|---|
| 0 Scaffold | done (owner confirmed /hooks) | make check exit 0; CI green | 2026-10-21 |
| 1 Ingest | done | make check, make dq, pytest -m idempotent exit 0; fixture committed | 2026-10-21 |
| 2 Analytics | done (/phase-check PASS, 0 blocking) | make check, make dq exit 0; crosscheck 10/10 exact | 2026-10-22 |
| 3 Search | done with D8 miss (owner accepted) | rerank recall@10 test 0.777 (< 0.80) | 2026-10-22 |
| 4 Answers | done (/phase-check PASS, 0 blocking) | make check 140 passed; make eval PASS: D5 100%, D6 100%, D7 98%, D9 92%, 6/6 | 2026-10-22 |
| 5 Web app | built; D12 missed, owner accepted; phase-check pending | make check 167 passed; make e2e 2 passed; make eval PASS, p95 9.8 s | 2026-10-22 |
| 6 Polish | not started | – | – |

## Blockers / decisions needed
- OS decided: native Windows with Git Bash; uv, make, jq, gh installed via winget (restart the terminal so PATH picks them up)
- Confirm LLM choice (default: Anthropic API, Haiku planner + Sonnet writer)
