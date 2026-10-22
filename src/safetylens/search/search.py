"""Rank a vehicle's complaints against a plain-English problem: BM25, dense, or both fused.

Why reciprocal rank fusion: BM25 scores and cosine similarities live on different scales, so adding
them is meaningless. RRF only uses each list's ranks: score = sum of 1 / (60 + rank). A complaint
near the top of either list rises; one near the top of both rises most.
"""

from collections import defaultdict
from collections.abc import Sequence
from typing import Any, Literal

import duckdb
from pydantic import BaseModel

from safetylens.analytics.templates import VehicleFilter
from safetylens.search.embed import Embedder
from safetylens.search.index import load_fts
from safetylens.store.sql import load_sql

Method = Literal["bm25", "dense", "hybrid"]
RRF_K = 60
POOL = 50  # how deep each list goes before fusion


class SearchHit(BaseModel):
    odino: str
    rank: int
    method: Method
    score: float


def rrf(rankings: Sequence[Sequence[str]], k: int = RRF_K) -> list[tuple[str, float]]:
    """Fuse ranked lists of ids; ties broken by id so results are deterministic."""
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def _ranked(
    con: duckdb.DuckDBPyConnection, name: str, params: dict[str, Any]
) -> list[tuple[str, float]]:
    return [(str(r[0]), float(r[1])) for r in con.execute(load_sql(name), params).fetchall()]


def bm25(
    con: duckdb.DuckDBPyConnection, f: VehicleFilter, query: str, k: int
) -> list[tuple[str, float]]:
    load_fts(con)
    return _ranked(con, "search_bm25", {**f.params(), "query": query, "k": k})


def dense(
    con: duckdb.DuckDBPyConnection, f: VehicleFilter, query: str, k: int, embedder: Embedder
) -> list[tuple[str, float]]:
    params = {**f.params(), "qvec": embedder.embed_query(query), "model": embedder.name, "k": k}
    return _ranked(con, "search_dense", params)


def search(
    con: duckdb.DuckDBPyConnection,
    f: VehicleFilter,
    query: str,
    *,
    method: Method = "hybrid",
    k: int = 8,
    embedder: Embedder | None = None,
) -> list[SearchHit]:
    if method not in ("bm25", "dense", "hybrid"):
        raise ValueError(f"unknown search method {method!r}")
    if method == "bm25":
        ranked = bm25(con, f, query, k)
    else:
        if embedder is None:
            raise ValueError(f"{method} search needs an embedder")
        if method == "dense":
            ranked = dense(con, f, query, k, embedder)
        else:
            lists = [
                [doc for doc, _ in bm25(con, f, query, POOL)],
                [doc for doc, _ in dense(con, f, query, POOL, embedder)],
            ]
            ranked = rrf(lists)[:k]
    return [
        SearchHit(odino=doc, rank=i, method=method, score=score)
        for i, (doc, score) in enumerate(ranked, start=1)
    ]


def snippet(con: duckdb.DuckDBPyConnection, odino: str, chars: int = 140) -> str:
    """Start of a complaint's narrative for display. Never logged (CLAUDE.md logging rule)."""
    row = con.execute(load_sql("narrative_snippet"), {"odino": odino, "chars": chars}).fetchone()
    return "" if row is None else str(row[0])
