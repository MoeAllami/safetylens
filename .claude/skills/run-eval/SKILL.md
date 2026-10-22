---
name: run-eval
description: Run the SafetyLens golden-question eval and compare it with the previous report. Use when the owner types /run-eval or asks how answer quality changed.
disable-model-invocation: true
allowed-tools: Bash(make eval) Bash(make eval-retrieval) Bash(ls *)
---

1. Run `make eval` (and `make eval-retrieval` if anything under `src/safetylens/search/` changed since the last report).
2. Open the newest and second-newest files in `evals/reports/`.
3. Report a table: check | previous | now | target (numbers_grounded, citations_valid, citations_supportive, golden pass rate, refusals, p50/p95 latency, mean cost per question).
4. List every question that went from pass to fail, with the failing check and a one-line hypothesis.
5. Never edit `evals/golden.yaml` to improve a score. If a golden item looks wrong, say why and ask the owner.
