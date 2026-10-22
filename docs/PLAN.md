# SafetyLens plan (execution copy for Claude Code)

Full plan with rationale and diagrams: the "Vehicle Safety Intelligence Platform — Project Plan" doc.
This file is the part Claude Code needs to execute. If they disagree, ask the owner.

## Goal
Local Python web app: ingest NHTSA complaints + recalls flat files → DuckDB → answer plain-English
questions with counts from SQL and citations to real records (ODI numbers, recall campaign numbers).

Example questions:
- "What are the most common brake complaints for 2022 Ford F-150s?" → ranked components with counts + 3–5 cited complaints
- "Are there recalls for the 2021 Honda CR-V airbags?" → campaigns with numbers and remedy
- "How did Tesla Model Y steering complaints trend by month in 2024?" → chart + cited examples from peak months
- "Is the Ford Maverick safe?" / "Which truck should I buy?" → refuse a verdict, offer facts

## Question pipeline
1. Plan: planner model → `QueryPlan` (vehicle, year range, component filter, intent ∈ {top_components, trend, recalls, examples, compare, out_of_scope}, time window)
2. Resolve vehicle via alias table + rapidfuzz; ambiguous → clarifying question
3. Compute: parameterized SQL template per intent (no LLM-written SQL)
4. Retrieve: filter by vehicle/component, hybrid BM25 + embeddings, reciprocal rank fusion, top 8
5. Write: writer model gets SQL rows + evidence, returns JSON {answer_markdown, citations[]}
6. Validate: citations ⊆ evidence ∩ DB; every number ∈ SQL rows (plan years/dates whitelisted); fail → retry once with error → deterministic template answer
7. Render: answer, count table, Altair chart, footnote citations → record pages

## Definition of done (all proven by commands)
| # | Criterion | Threshold | Proven by |
|---|---|---|---|
| D1 | One-command setup | `uv sync && make data-dev && make serve` on clean machine | `scripts/fresh_clone_check.sh` |
| D2 | Idempotent ingest | 2nd run: identical row counts + checksums | `pytest tests/ingest -m idempotent` |
| D3 | Data quality | 0 missing ODINO; 0 duplicate (odino, component); PII columns absent | `make dq` |
| D4 | Counts match NHTSA | 10 vehicles within 2% of live complaintsByVehicle API (distinct ODI) | `make crosscheck` |
| D5 | Numbers grounded | 100% | eval `numbers_grounded` |
| D6 | Citations valid | 100% | eval `citations_valid` |
| D7 | Citations supportive | ≥ 90% | eval `citations_supportive` |
| D8 | Retrieval | hybrid recall@10 ≥ 0.80, beats BM25-only and dense-only | `make eval-retrieval` |
| D9 | Golden set | ≥ 85% of 40 pass; 6/6 out-of-scope refused | `make eval` |
| D10 | Code health | ruff, mypy --strict src, coverage ≥ 80%, 0 failures | `make check` |
| D11 | UI end to end | ask → answer → citation → record page → NHTSA link | `make e2e` |
| D12 | Latency | p95 < 8 s (warm, dev slice) | eval report |
| D13 | Cost bounded | mean cost/question reported; daily cap enforced + tested | eval report + unit test |
| D14 | Documented | README: setup, diagram, data card, eval table, limitations, demo GIF | `scripts/check_docs.py` |
| D15 | Safe repo | no secrets (gitleaks), `.env` ignored, disclaimer + attribution in UI | CI + e2e assertion |

## Phases and gates
- **Phase 0 – Scaffold (wk 1).** uv project, ruff/mypy/pytest/pre-commit, Makefile with all targets (stubs fail until built), GitHub Actions CI (lint, types, tests on fixture, gitleaks), `.env.example`, `.gitignore` (data/, .env, .claude/.last_green, .claude/.unlock-protected, .claude/settings.local.json). Gate: `make check` green with one smoke test; CI green; `/hooks` lists project hooks.
- **Phase 1 – Ingest (wk 1–2).** `safetylens ingest --slice dev|full`: download with checksum + If-Modified-Since, parse by position (49 or 51 fields), drop PII, Parquet → DuckDB `complaints_raw`, `recalls_raw`, `ingest_runs`; 2,000-row committed fixture. Gate: `make dq`; `pytest tests/ingest -m idempotent`.
- **Phase 2 – Normalize + analytics (wk 3).** `complaints` (one row per odino×component), `complaint_docs` (one per odino), `component_system`, model alias table, SQL templates (top components, monthly trend, severity, recalls by vehicle), `make crosscheck`. Gate: golden-output test per template; crosscheck within 2%.
- **Phase 3 – Search (wk 4).** DuckDB fts BM25, bge-small-en-v1.5 embeddings (batched, resumable), hybrid RRF, `safetylens search`; 60 labeled queries in `evals/retrieval_labels.yaml` (Claude drafts, owner verifies). Gate: D8.
- **Phase 4 – Answer engine + evals (wk 5–6).** planner, resolver, compute, writer, validator, budget guard, `safetylens ask`; `evals/golden.yaml` (34 answerable + 6 out-of-scope, expected facts); eval runner → `evals/reports/<date>.md`. Gate: D5, D6, D7, D9, D13; unit tests use FakeLLM only.
- **Phase 5 – Web app (wk 7–8).** FastAPI + Jinja2 + HTMX + Pico.css: `/`, `/ask` (partial), `/complaint/{odi}`, `/recall/{campaign}`, `/vehicle/{make}/{model}/{year}`; Altair charts; disclaimer; Playwright. Run `/run-skill-generator` once the app starts. Gate: D11, D12.
- **Phase 6 – Harden (wk 9–10).** answer cache (key = normalized plan), structlog, error pages, Dockerfile (build only), README + data card + eval table + demo GIF, `make acceptance`. Gate: D1–D15 on fresh clone.

## Eval checks (make eval)
- numbers_grounded: regex all numbers in answer; each in SQL rows (plan years/dates whitelisted)
- citations_valid: every [ODI]/[campaign] in evidence set and DB
- citations_supportive: LLM judge on (claim, cited narrative); owner spot-checks 10 per phase
- expected_facts: checked against structured result, not prose
- refusal_correct: out-of-scope → refusal template, zero citations
Report also: p50/p95 latency, mean cost per question.

## Suggested /goal per phase
`/goal <phase gate commands> exit 0 as shown in the transcript; no file under evals/golden.yaml, evals/retrieval_labels.yaml or tests/fixtures is modified; or stop after 30 turns`
