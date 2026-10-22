"""Write judging worksheets: per eval query, the union of the top 20 from BM25, dense and hybrid.

Why pooling: judging all ~1,000 complaints per vehicle is too much, so we judge only what at least
one method ranks highly (standard TREC practice). Worksheets contain narratives, so they go to
data/judging/ (git-ignored) and never into the repo.

Usage: uv run python scripts/pool_candidates.py   (after `make data-dev`)
"""

import json
from pathlib import Path

from safetylens.config import Settings
from safetylens.ingest.pipeline import DB_NAME
from safetylens.search.embed import default_embedder
from safetylens.search.evaluate import load_queries, pool
from safetylens.store import db
from safetylens.store.sql import load_sql

QUERIES = Path("evals/retrieval_queries.yaml")
OUT = Path("data/judging")
DEPTH = 20
MAX_CHARS = 1500


def main() -> None:
    settings = Settings()
    embedder = default_embedder(
        settings.embed_model, settings.embed_device, settings.embed_batch_size
    )
    OUT.mkdir(parents=True, exist_ok=True)
    with db.connect(settings.data_dir / DB_NAME, read_only=True) as con:
        for q in load_queries(QUERIES):
            candidates = pool(con, q, embedder, depth=DEPTH)
            rows = con.execute(load_sql("narratives_for"), [candidates]).fetchall()
            text = {str(r[0]): str(r[1])[:MAX_CHARS] for r in rows}
            sheet = {
                "id": q.id,
                "vehicle": f"{q.year} {q.make} {q.model}",
                "query": q.query,
                "candidates": [
                    {"odino": c, "narrative": text.get(c, "")} for c in sorted(candidates)
                ],
            }
            (OUT / f"{q.id}.json").write_text(json.dumps(sheet, indent=1), encoding="utf-8")
            print(f"{q.id}: {len(candidates)} candidates")


if __name__ == "__main__":
    main()
