---
name: phase-check
description: Run a SafetyLens phase gate, get an independent review, and update PROGRESS.md. Use only when the owner types /phase-check N.
argument-hint: "[phase-number 0-6]"
disable-model-invocation: true
---

Check whether Phase $ARGUMENTS is done.

## Gates (from docs/PLAN.md)
| Phase | Gate commands (all must exit 0) |
|---|---|
| 0 | `make check`; `gh run list --limit 1` shows success; `/hooks` lists the project hooks |
| 1 | `make check`; `make dq`; `uv run pytest tests/ingest -m idempotent` |
| 2 | `make check`; `make crosscheck` (within 2% for all 10 vehicles) |
| 3 | `make check`; `make eval-retrieval` (hybrid recall@10 >= 0.80 and beats BM25-only and dense-only) |
| 4 | `make check`; `make eval` (numbers_grounded 100%, citations_valid 100%, citations_supportive >= 90%, golden pass >= 85%, refusals 6/6) |
| 5 | `make check`; `make e2e`; p95 latency < 8 s in the latest eval report |
| 6 | `make acceptance` on a fresh clone (`scripts/fresh_clone_check.sh`) |

## Steps
1. Run each gate command for Phase $ARGUMENTS. Paste the exact command and the last 15 lines of output for each.
2. Ask the `reviewer` subagent to review `git diff main...HEAD` against CLAUDE.md and the phase's deliverables in docs/PLAN.md. Include its findings verbatim, grouped as blocking / non-blocking.
3. List every `TODO(you)` stub in the code (`grep -rn "TODO(you)" src tests`) and whether its test passes.
4. Verdict: PASS only if every gate command exited 0, the reviewer found no blocking issue, and all TODO(you) tests pass. Otherwise FAIL with the shortest list of what is missing.
5. Update `docs/PROGRESS.md`: mark the phase, record measured numbers (row counts, recall@10, eval rates, latency, cost), and write the next phase's first three tasks.
6. Give the owner a 3-step manual demo to try for this phase, then suggest `/learn`.

Do not edit code during this skill. It only checks and reports.
