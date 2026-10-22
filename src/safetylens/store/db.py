"""DuckDB access for the raw layer.

Why replace-not-append: each load rebuilds a raw table from the Parquet files in one transaction,
so running ingest twice gives identical rows instead of duplicates (the idempotency gate, D2).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import duckdb

from safetylens.ingest.sources import Kind
from safetylens.store.sql import load_sql

_LOAD_SQL = {"complaints": "load_complaints_raw", "recalls": "load_recalls_raw"}
_SUMMARY_SQL = {"complaints": "summary_complaints_raw", "recalls": "summary_recalls_raw"}


@dataclass(frozen=True)
class TableSummary:
    row_count: int
    distinct_keys: int  # distinct ODINO for complaints, distinct CAMPNO for recalls
    checksum: str


def connect(path: Path, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    if not read_only:
        path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path), read_only=read_only)
    if not read_only:
        con.execute(load_sql("create_ingest_runs"))
        con.execute(load_sql("migrate_ingest_runs_cp1252"))
    return con


def load_raw_table(
    con: duckdb.DuckDBPyConnection, kind: Kind, parquet_files: Sequence[Path]
) -> None:
    files = [p.as_posix() for p in parquet_files]
    con.begin()
    try:
        con.execute(load_sql(_LOAD_SQL[kind]), [files])
    except BaseException:
        con.rollback()
        raise
    con.commit()


def summarize(con: duckdb.DuckDBPyConnection, kind: Kind) -> TableSummary:
    row = con.execute(load_sql(_SUMMARY_SQL[kind])).fetchone()
    if row is None:
        raise RuntimeError(f"summary for {kind} returned no row")
    return TableSummary(int(row[0]), int(row[1]), str(row[2]))


def count_rows(con: duckdb.DuckDBPyConnection, table: str) -> int:
    """Row count of a table, passing its name as a bound parameter to query_table()."""
    row = con.execute(load_sql("count_rows"), [table]).fetchone()
    if row is None:
        raise RuntimeError(f"count of {table} returned no row")
    return int(row[0])


def record_run(con: duckdb.DuckDBPyConnection, values: Sequence[object]) -> None:
    con.execute(load_sql("insert_ingest_run"), list(values))
