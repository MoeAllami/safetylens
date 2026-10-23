"""Glue: download -> parse -> Parquet -> DuckDB, for one slice.

Why a sidecar stats file: parsing millions of rows is the slow step, so when a zip is unchanged
(same sha256, same layout) we reuse its Parquet instead of reparsing.
"""

import dataclasses
import datetime as dt
import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path

import duckdb
import httpx
import structlog

from safetylens.config import Settings
from safetylens.ingest.download import download, use_downloaded
from safetylens.ingest.flatfile import PARSER_VERSION, Column, ParseStats, parse_zip_to_parquet
from safetylens.ingest.layouts import (
    COMPLAINT_COLUMNS,
    COMPLAINT_FIELD_COUNTS,
    RECALL_COLUMNS,
    RECALL_FIELD_COUNTS,
)
from safetylens.ingest.sources import Kind, Source, sources_for
from safetylens.store import db

log = structlog.get_logger()

DB_NAME = "safetylens.duckdb"
KINDS: tuple[Kind, ...] = ("complaints", "recalls")


@dataclass(frozen=True)
class SourceReport:
    source: Source
    download_status: str
    sha256: str
    stats: ParseStats


def _layout(kind: Kind) -> tuple[tuple[Column, ...], frozenset[int]]:
    if kind == "complaints":
        return COMPLAINT_COLUMNS, COMPLAINT_FIELD_COUNTS
    return RECALL_COLUMNS, RECALL_FIELD_COUNTS


def _layout_id(columns: tuple[Column, ...], counts: frozenset[int]) -> str:
    # PARSER_VERSION is part of the id so a parser change forces a reparse of unchanged zips.
    spec = (PARSER_VERSION, columns, sorted(counts))
    return hashlib.sha256(repr(spec).encode()).hexdigest()[:16]


def _parse_if_needed(source: Source, zip_path: Path, sha256: str, parquet_dir: Path) -> ParseStats:
    columns, counts = _layout(source.kind)
    layout_id = _layout_id(columns, counts)
    parquet = parquet_dir / f"{source.name}.parquet"
    sidecar = parquet_dir / f"{source.name}.stats.json"
    if parquet.exists() and sidecar.exists():
        saved = json.loads(sidecar.read_text(encoding="utf-8"))
        if saved["sha256"] == sha256 and saved["layout_id"] == layout_id:
            return ParseStats(**saved["stats"])
    stats = parse_zip_to_parquet(zip_path, parquet, columns, counts)
    payload = {"sha256": sha256, "layout_id": layout_id, "stats": dataclasses.asdict(stats)}
    sidecar.write_text(json.dumps(payload), encoding="utf-8")
    return stats


def run_ingest(
    settings: Settings, slice_name: str, client: httpx.Client | None
) -> tuple[list[SourceReport], duckdb.DuckDBPyConnection]:
    """client=None means offline: load the zips already downloaded (checksums verified)."""
    sources = sources_for(slice_name)
    raw_dir = settings.data_dir / "raw"
    parquet_dir = settings.data_dir / "parquet"
    reports: list[SourceReport] = []
    for source in sources:
        if client is None:
            result = use_downloaded(source, raw_dir)
        else:
            result = download(client, source, raw_dir)
        stats = _parse_if_needed(source, result.path, result.sha256, parquet_dir)
        log.info("parsed", source=source.name, **dataclasses.asdict(stats))
        reports.append(SourceReport(source, result.status, result.sha256, stats))

    con = db.connect(settings.data_dir / DB_NAME)
    run_id = uuid.uuid4().hex
    started = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    for kind in KINDS:
        files = [parquet_dir / f"{r.source.name}.parquet" for r in reports if r.source.kind == kind]
        if files:
            db.load_raw_table(con, kind, files)
    for r in reports:
        db.record_run(
            con,
            [
                run_id,
                started,
                r.source.name,
                r.source.kind,
                r.download_status,
                r.sha256,
                r.stats.rows_read,
                r.stats.rows_loaded,
                r.stats.rows_rejected,
                r.stats.rows_replaced,
                r.stats.bad_values,
                r.stats.rows_cp1252,
            ],
        )
    return reports, con
