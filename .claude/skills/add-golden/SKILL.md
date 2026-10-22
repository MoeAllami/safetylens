---
name: add-golden
description: Draft a new golden eval question with expected facts computed from the database. Use when the owner types /add-golden "question".
argument-hint: "\"question text\""
disable-model-invocation: true
---

Draft a golden eval item for: $ARGUMENTS

1. Decide the intent (top_components, trend, recalls, examples, compare, out_of_scope) and the vehicle.
2. Write the SQL that computes the expected facts using the templates in `src/safetylens/store/queries/`. Run it with `uv run safetylens sql --file <tmp.sql>` (or DuckDB CLI) and show the query and result to the owner.
3. Propose the YAML entry in this shape and show it, without writing it:

```yaml
- id: g041
  question: "..."
  intent: top_components
  vehicle: {make: FORD, model: F-150, year_from: 2022, year_to: 2022}
  expected_facts:
    top_component_system: SERVICE BRAKES
    min_distinct_complaints: 120
  must_cite: true
  notes: "why this question matters"
```

4. `evals/golden.yaml` is protected. Ask the owner to unlock it (`touch .claude/.unlock-protected`), append the entry only after they say yes, then remind them to delete the unlock file.
