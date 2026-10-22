"""Stream NHTSA tab-delimited flat files from a zip into Parquet.

Why one generic parser: complaints and recalls share a format (TAB, no header, cp1252), and a
layout can only ever read the columns it lists, so personal data is dropped in exactly one place.
"""

import datetime as dt
import io
import zipfile
from collections.abc import Collection, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pyarrow as pa
import pyarrow.parquet as pq

ColumnKind = Literal["str", "int", "date"]

BATCH_ROWS = 50_000
REPLACEMENT_CHAR = "�"
_ARROW_TYPES: dict[ColumnKind, pa.DataType] = {
    "str": pa.string(),
    "int": pa.int32(),
    "date": pa.date32(),
}


@dataclass(frozen=True)
class Column:
    name: str
    position: int  # 1-based, exactly as numbered in the NHTSA data dictionary
    kind: ColumnKind = "str"


@dataclass
class ParseStats:
    rows_read: int = 0
    rows_loaded: int = 0
    rows_rejected: int = 0  # wrong field count
    rows_replaced: int = 0  # rows that contained undecodable bytes
    bad_values: int = 0  # unparseable numbers or dates, stored as NULL


def _convert(raw: str | None, kind: ColumnKind, stats: ParseStats) -> object:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    if kind == "str":
        return text
    try:
        if kind == "int":
            return int(text)
        if len(text) != 8 or not text.isdigit():
            raise ValueError(text)
        return dt.date(int(text[:4]), int(text[4:6]), int(text[6:]))
    except ValueError:
        stats.bad_values += 1
        return None


def _iter_lines(zf: zipfile.ZipFile, member: str) -> Iterator[str]:
    with zf.open(member) as raw:
        # newline="\n" splits only on LF, so a stray CR inside a field never starts a new record.
        text = io.TextIOWrapper(raw, encoding="cp1252", errors="replace", newline="\n")
        yield from text


def _flush(writer: pq.ParquetWriter, schema: pa.Schema, buffers: list[list[object]]) -> None:
    arrays = [pa.array(b, type=schema.field(i).type) for i, b in enumerate(buffers)]
    writer.write_table(pa.Table.from_arrays(arrays, schema=schema))
    for b in buffers:
        b.clear()


def parse_zip_to_parquet(
    zip_path: Path,
    out_path: Path,
    columns: Sequence[Column],
    field_counts: Collection[int],
) -> ParseStats:
    schema = pa.schema([(c.name, _ARROW_TYPES[c.kind]) for c in columns])
    wanted = [(c.position - 1, c.kind) for c in columns]
    stats = ParseStats()
    buffers: list[list[object]] = [[] for _ in columns]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(out_path.name + ".part")
    try:
        with (
            zipfile.ZipFile(zip_path) as zf,
            pq.ParquetWriter(tmp, schema, compression="zstd") as writer,
        ):
            for member in sorted(n for n in zf.namelist() if n.lower().endswith(".txt")):
                for line in _iter_lines(zf, member):
                    record = line.rstrip("\r\n")
                    if not record.strip():
                        continue
                    stats.rows_read += 1
                    if REPLACEMENT_CHAR in record:
                        stats.rows_replaced += 1
                    fields = record.split("\t")
                    if len(fields) not in field_counts:
                        stats.rows_rejected += 1
                        continue
                    # Only listed positions are ever read; anything else (VIN, city...) is dropped.
                    for buf, (idx, kind) in zip(buffers, wanted, strict=True):
                        raw = fields[idx] if idx < len(fields) else None
                        buf.append(_convert(raw, kind, stats))
                    stats.rows_loaded += 1
                    if len(buffers[0]) >= BATCH_ROWS:
                        _flush(writer, schema, buffers)
            if buffers[0]:
                _flush(writer, schema, buffers)
        tmp.replace(out_path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return stats
