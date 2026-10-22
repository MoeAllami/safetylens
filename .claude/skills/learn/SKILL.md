---
name: learn
description: Teach-back session - explain the concepts used since the last LEARNING.md entry, quiz the owner, and record their answers. Use when the owner types /learn.
disable-model-invocation: true
---

The owner is a recent grad using this project to learn. Run a short teach-back:

1. Read the last entry in `docs/LEARNING.md` and `git log --oneline` since that date.
2. Pick the 3 most important concepts introduced since then (for example: idempotent ingest, BM25 vs embeddings, reciprocal rank fusion, structured outputs, prompt caching, HTMX partials).
3. For each: explain it in at most 4 sentences, pointing to the exact file and function in this repo where it lives.
4. Ask 3 questions, one per concept, that require reasoning rather than recall (for example: "What would break if we counted complaints with COUNT(*)?"). Ask them one at a time and wait for each answer.
5. Give honest feedback on each answer: what was right, what was missing.
6. Append to `docs/LEARNING.md` a dated entry: concepts, the owner's answers in their words, your feedback, and one suggested reading link per concept.

Do not answer the questions for the owner.
