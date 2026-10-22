# SafetyLens — Claude Code project memory

## What this is
A Python web app that ingests NHTSA vehicle complaint and recall flat files into DuckDB,
analyzes them, and answers plain-English questions with citations to real records
(complaint ODI numbers, recall campaign numbers). Side project for learning; the owner
is a recent grad who wants to understand every part. Full plan: `docs/PLAN.md`.
Current phase and open items: `docs/PROGRESS.md` (read it at the start of every session).

## Non-negotiable rules
1. **Numbers come from SQL, words come from records.** The LLM never produces a count,
   rate, or date that is not in a SQL result it was given. The validator enforces this.
2. **Only cite what was retrieved.** Every `[ODI]` or `[campaign]` citation must be in the
   evidence set passed to the writer and exist in the DB.
3. **Count complaints with `COUNT(DISTINCT odino)`**, never `COUNT(*)` — ODINO repeats per component.
4. **Privacy:** `VIN`, `VEHICLE_OPERATOR`, `CITY`, `DEALER_*` are dropped at ingest. They never
   reach DuckDB, prompts, logs, or the UI.
5. **No LLM-written SQL in v1.** Use parameterized templates in `src/safetylens/store/queries/`.
6. **Never weaken a check to make it pass.** Do not edit `evals/golden.yaml`,
   `evals/retrieval_labels.yaml`, or `tests/fixtures/` without asking the owner first
   (a hook blocks it). If a test is wrong, say so and propose the change.
7. **Unit tests never call the network or a paid API.** Use `FakeLLM` and `respx`.
   Mark anything else `@pytest.mark.network` or `@pytest.mark.slow`.
8. Use `uv add <pkg>` for dependencies, never `pip install`.

## Learning mode (the owner is here to learn)
- Before introducing a new concept or library, explain it in at most 3 sentences.
- After a phase gate passes, suggest running `/learn`.
- Prefer clear code over clever code; add a short docstring saying *why*, not *what*.

## Commands
- `uv sync` — install
- `make check` — ruff, ruff format --check, mypy --strict src, pytest with coverage ≥ 80%
- `make test-fast` — `uv run pytest -m "not slow and not network" -x -q`
- `make data-dev` — ingest the 2020–2026 slice; `make data-full` — everything
- `make dq` — data-quality report; `make crosscheck` — compare counts with live NHTSA API
- `make eval-retrieval`, `make eval`, `make e2e`, `make acceptance`
- `uv run safetylens --help` — CLI (ingest, index, search, ask, eval, serve)

## Stack
Python 3.12, uv, DuckDB (+ fts), sentence-transformers (bge-small-en-v1.5), rapidfuzz,
Anthropic SDK (planner and writer model names come from settings, never hard-coded),
FastAPI + Jinja2 + HTMX + Pico.css, Altair, Typer, pydantic-settings, pytest, Playwright.

## Code conventions
- `src/` layout, package `safetylens`. Type hints everywhere; `mypy --strict` must pass.
- Pydantic models for anything crossing a boundary (QueryPlan, Evidence, Answer).
- SQL lives in `.sql` files, loaded by name. Parameters only, no f-string SQL.
- Small modules (< 300 lines). One responsibility each.
- Logging via `structlog`; never log narratives or anything from rule 4.

## Workflow
- One branch and one PR per phase: `phase-N-short-name`.
- Start each phase in plan mode. Show the plan; wait for approval.
- A phase is done only when its gate command exits 0 and `/phase-check N` passes.
  Report the exact command and its output, not a summary of it.
- Update `docs/PROGRESS.md` at the end of every session: done, next, blockers, TODO(you) list.
- Data details (field positions, gotchas, URLs) are in the `nhtsa-data` skill — load it
  before touching ingest, normalize, or SQL.
