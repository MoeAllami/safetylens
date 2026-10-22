"""Build the search indexes: the BM25 full-text index and the embedding table.

Why chunks with a commit each: embedding 400k narratives takes minutes. If it is interrupted, the
next run continues where it stopped (docs_to_embed only returns what is missing or changed).
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

import duckdb
import pyarrow as pa

from safetylens.search.embed import Embedder
from safetylens.store.db import count_rows
from safetylens.store.sql import load_sql

CHUNK_DOCS = 4096


def load_fts(con: duckdb.DuckDBPyConnection) -> None:
    """Load the fts extension from the local cache; never downloads (see `make install`)."""
    try:
        con.load_extension("fts")
    except duckdb.Error as exc:
        raise RuntimeError("DuckDB fts extension is not installed; run `make install`") from exc


def build_fts(con: duckdb.DuckDBPyConnection) -> None:
    load_fts(con)
    con.execute(load_sql("fts_create"))


@dataclass(frozen=True)
class EmbedStats:
    embedded: int
    already_current: int
    seconds: float

    @property
    def docs_per_second(self) -> float:
        return self.embedded / self.seconds if self.seconds > 0 else 0.0


def _store_chunk(
    con: duckdb.DuckDBPyConnection,
    rows: list[tuple[str, str, str]],
    vectors: list[list[float]],
    model: str,
) -> None:
    batch = pa.table(
        {
            "odino": [r[0] for r in rows],
            "text_sha": [r[2] for r in rows],
            "model": [model] * len(rows),
            "embedding": pa.array(vectors, type=pa.list_(pa.float32())),
        }
    )
    con.register("embed_batch", batch)
    try:
        con.begin()
        try:
            con.execute(load_sql("delete_embeddings_in_batch"))
            con.execute(load_sql("insert_embeddings_from_batch"))
        except BaseException:
            con.rollback()
            raise
        con.commit()
    finally:
        con.unregister("embed_batch")


def embed_docs(
    con: duckdb.DuckDBPyConnection,
    embedder: Embedder,
    *,
    chunk: int = CHUNK_DOCS,
    on_progress: Callable[[int, int], None] | None = None,
) -> EmbedStats:
    con.execute(load_sql("create_doc_embeddings"))
    todo = [
        r[0] for r in con.execute(load_sql("docs_to_embed"), {"model": embedder.name}).fetchall()
    ]
    total = count_rows(con, "complaint_docs")
    start = time.perf_counter()
    done = 0
    for i in range(0, len(todo), chunk):
        rows = con.execute(load_sql("narratives_for"), [todo[i : i + chunk]]).fetchall()
        vectors = embedder.embed_documents([r[1] for r in rows])
        _store_chunk(con, rows, vectors, embedder.name)
        done += len(rows)
        if on_progress is not None:
            on_progress(done, len(todo))
    return EmbedStats(
        embedded=done, already_current=total - len(todo), seconds=time.perf_counter() - start
    )
