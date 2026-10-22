import datetime as dt
import zipfile
from pathlib import Path

import pyarrow.parquet as pq
from builders import PII_MARKERS, complaint_line, recall_line, write_zip

from safetylens.ingest.flatfile import parse_zip_to_parquet
from safetylens.ingest.layouts import (
    COMPLAINT_COLUMNS,
    COMPLAINT_FIELD_COUNTS,
    RECALL_COLUMNS,
    RECALL_FIELD_COUNTS,
)


def _parse_complaints(tmp_path: Path, lines: list[str], newline: str = "\r\n"):  # type: ignore[no-untyped-def]
    zip_path = write_zip(tmp_path / "c.zip", "C.txt", lines, newline=newline)
    out = tmp_path / "c.parquet"
    stats = parse_zip_to_parquet(zip_path, out, COMPLAINT_COLUMNS, COMPLAINT_FIELD_COUNTS)
    return stats, pq.read_table(out)


def test_parses_51_and_49_field_rows(tmp_path: Path) -> None:
    lines = [complaint_line("1", n_fields=51), complaint_line("2", n_fields=49)]
    stats, table = _parse_complaints(tmp_path, lines)
    assert stats.rows_loaded == 2
    rows = {r["odino"]: r for r in table.to_pylist()}
    assert rows["1"]["state_of_incident"] == "TX"
    assert rows["2"]["state_of_incident"] is None  # field 50 does not exist in 49-field files


def test_types_and_blanks(tmp_path: Path) -> None:
    stats, table = _parse_complaints(tmp_path, [complaint_line(p9="", p8="00000000")])
    row = table.to_pylist()[0]
    assert row["ldate"] == dt.date(2022, 3, 9)
    assert row["miles"] == 12000
    assert row["fire"] is None  # blank text becomes NULL
    assert row["faildate"] is None
    assert stats.bad_values == 1  # the impossible date 00000000 is counted, not silently dropped


def test_pii_never_reaches_parquet(tmp_path: Path) -> None:
    _, table = _parse_complaints(tmp_path, [complaint_line()])
    text = repr(table.to_pylist())
    for marker in PII_MARKERS.values():
        assert marker not in text
    for forbidden in ("city", "vin", "vehicle_operator", "dealer_name", "dealer_zip"):
        assert forbidden not in table.column_names


def test_utf8_first_then_cp1252_fallback_per_line(tmp_path: Path) -> None:
    zip_path = tmp_path / "c.zip"
    utf8 = complaint_line("1", narrative="DRIVER’S SIDE").encode("utf-8")
    cp1252 = complaint_line("2", narrative="CAFÉ").encode("cp1252")  # \xc9 is invalid UTF-8
    undefined = complaint_line("3", narrative="XX").replace("XX", "A\x81B").encode("latin-1")
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("C.txt", b"\xef\xbb\xbf" + b"\r\n".join([utf8, cp1252, undefined]) + b"\r\n")
    out = tmp_path / "c.parquet"
    stats = parse_zip_to_parquet(zip_path, out, COMPLAINT_COLUMNS, COMPLAINT_FIELD_COUNTS)
    narratives = {r["odino"]: r["cdescr"] for r in pq.read_table(out).to_pylist()}
    assert narratives["1"] == "DRIVER’S SIDE"  # not the mojibake "DRIVERâ€™S"
    assert narratives["2"] == "CAFÉ"
    assert "�" in narratives["3"]  # 0x81 is undefined even in cp1252
    assert (stats.rows_loaded, stats.rows_cp1252, stats.rows_replaced) == (3, 2, 1)


def test_wrong_field_count_is_rejected_and_counted(tmp_path: Path) -> None:
    lines = [complaint_line("1"), "only\tthree\tfields", complaint_line("3", n_fields=50)]
    stats, table = _parse_complaints(tmp_path, lines)
    assert (stats.rows_read, stats.rows_loaded, stats.rows_rejected) == (3, 1, 2)
    assert table.num_rows == 1


def test_missing_odino_is_kept_as_null_so_dq_can_see_it(tmp_path: Path) -> None:
    stats, table = _parse_complaints(tmp_path, [complaint_line(None)])
    assert stats.rows_loaded == 1
    assert table.to_pylist()[0]["odino"] is None


def test_recalls_parse_and_lf_line_endings(tmp_path: Path) -> None:
    zip_path = write_zip(
        tmp_path / "r.zip", "R.txt", [recall_line("22V1"), recall_line("22V2")], newline="\n"
    )
    out = tmp_path / "r.parquet"
    stats = parse_zip_to_parquet(zip_path, out, RECALL_COLUMNS, RECALL_FIELD_COUNTS)
    assert stats.rows_loaded == 2
    assert sorted(r["campno"] for r in pq.read_table(out).to_pylist()) == ["22V1", "22V2"]
