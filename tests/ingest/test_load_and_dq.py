from pathlib import Path

import httpx
import pytest
import respx
from builders import complaint_line, recall_line, write_zip

from safetylens.config import Settings
from safetylens.dq import run_checks
from safetylens.ingest import pipeline
from safetylens.ingest.sources import Source
from safetylens.store import db

COMPLAINT_SRC = Source("C_TEST", "complaints", "https://example.test/C_TEST.zip")
RECALL_SRC = Source("R_TEST", "recalls", "https://example.test/R_TEST.zip")


def _serve(tmp_path: Path, complaint_lines: list[str]) -> None:
    c = write_zip(tmp_path / "c_src.zip", "C.txt", complaint_lines)
    r = write_zip(tmp_path / "r_src.zip", "R.txt", [recall_line("22V1"), recall_line("22V2")])
    respx.get(COMPLAINT_SRC.url).respond(200, content=c.read_bytes(), headers={"ETag": '"c"'})
    respx.get(RECALL_SRC.url).respond(200, content=r.read_bytes(), headers={"ETag": '"r"'})


@pytest.fixture
def small_slice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "sources_for", lambda _name: (COMPLAINT_SRC, RECALL_SRC))


def _settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path / "data")  # type: ignore[call-arg]


def _ingest(tmp_path: Path):  # type: ignore[no-untyped-def]
    with httpx.Client() as client:
        _, con = pipeline.run_ingest(_settings(tmp_path), "dev", client)
    return con


GOOD = [
    complaint_line("1", compdesc="SERVICE BRAKES, HYDRAULIC"),
    complaint_line("1", compdesc="STEERING"),  # same ODINO, second component
    complaint_line("2", n_fields=49),
]


@respx.mock
@pytest.mark.idempotent
@pytest.mark.usefixtures("small_slice")
def test_second_ingest_gives_identical_rows_and_checksums(tmp_path: Path) -> None:
    _serve(tmp_path, GOOD)
    con = _ingest(tmp_path)
    first = (db.summarize(con, "complaints"), db.summarize(con, "recalls"))
    con.close()

    con = _ingest(tmp_path)  # re-run: files are unchanged
    second = (db.summarize(con, "complaints"), db.summarize(con, "recalls"))
    runs = con.execute("SELECT count(*) FROM ingest_runs").fetchone()
    con.close()

    assert first == second
    assert first[0].row_count == 3
    assert first[0].distinct_keys == 2  # ODINO repeats per component: rows != complaints
    assert runs is not None
    assert runs[0] == 4  # ingest_runs is an append-only log: 2 sources x 2 runs


@respx.mock
@pytest.mark.usefixtures("small_slice")
def test_dq_passes_on_clean_data(tmp_path: Path) -> None:
    _serve(tmp_path, GOOD)
    con = _ingest(tmp_path)
    results = run_checks(con)
    assert all(r.passed for r in results), results


@respx.mock
@pytest.mark.usefixtures("small_slice")
def test_dq_fails_on_missing_odino_and_duplicates(tmp_path: Path) -> None:
    _serve(tmp_path, [*GOOD, complaint_line(None), GOOD[0]])
    con = _ingest(tmp_path)
    failed = {r.name for r in run_checks(con) if not r.passed}
    assert failed == {"0 missing ODINO", "0 duplicate (odino, component)"}


@respx.mock
@pytest.mark.usefixtures("small_slice")
def test_dq_fails_if_a_pii_column_exists(tmp_path: Path) -> None:
    _serve(tmp_path, GOOD)
    con = _ingest(tmp_path)
    con.execute("ALTER TABLE complaints_raw ADD COLUMN vin VARCHAR")
    result = next(r for r in run_checks(con) if r.name == "PII columns absent")
    assert not result.passed
    assert "complaints_raw.vin" in result.detail


def test_dq_reports_missing_tables(tmp_path: Path) -> None:
    con = db.connect(tmp_path / "empty.duckdb")
    results = run_checks(con)
    assert [r.passed for r in results] == [False]
