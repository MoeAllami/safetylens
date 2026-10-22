---
name: learn
description: Teach-back session - explain the concepts used since the last LEARNING.md entry, then give reasoning questions with full answers, and record them. Use when the owner types /learn.
disable-model-invocation: true
---

The owner is a recent grad using this project to learn. Run a short teach-back:

1. Read the last entry in `docs/LEARNING.md` and `git log --oneline` since that date.
2. Pick the 3 most important concepts introduced since then (for example: idempotent ingest, BM25 vs embeddings, reciprocal rank fusion, structured outputs, prompt caching, HTMX partials).
3. For each: explain it in at most 4 sentences, pointing to the exact file and function in this repo where it lives.
4. Give 3 questions, one per concept, that require reasoning rather than recall (for example: "What would break if we counted complaints with COUNT(*)?"). Present all of them at once, each followed by its full answer. Do not wait for the owner to answer.
5. In each answer, say what would break or why, which check or test in this repo would or would not catch it, and the one-line lesson.
6. Append to `docs/LEARNING.md` a dated entry: concepts, each question with its answer, and one suggested reading link per concept.

If the owner replies with their own take on a question, give honest feedback (what was right, what was missing) and add it to that entry.
