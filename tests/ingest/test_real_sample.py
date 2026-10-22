"""Run the committed real-data sample through the whole pipeline (no network: respx serves it).

Why: synthetic rows prove the rules; this proves them on what NHTSA actually ships (UTF-8 text,
multi-component and multi-product complaints, long narratives).
"""

import zipfile
from pathlib import Path

import httpx
import pytest
import respx

from safetylens.config import Settings
from safetylens.dq import run_checks
from safetylens.ingest import pipeline
from safetylens.ingest.sources import Source
from safetylens.store import db

FIXTURES = Path(__file__).parents[1] / "fixtures"
C = Source("C_SAMPLE", "complaints", "https://example.test/C_SAMPLE.zip")
R = Source("R_SAMPLE", "recalls", "https://example.test/R_SAMPLE.zip")
PII_POSITIONS = (13, 15, 41, 42, 43, 44, 45, 51)


def _zip(src: Path, dest: Path) -> bytes:
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(src.name, src.read_bytes())
    return dest.read_bytes()


def test_fixture_has_no_personal_data() -> None:
    lines = (FIXTURES / "complaints_sample.txt").read_bytes().split(b"\r\n")[:-1]
    assert len(lines) == 2000
    for line in lines:
        fields = line.split(b"\t")
        assert all(not fields[p - 1].strip() for p in PII_POSITIONS if p <= len(fields))


@respx.mock
def test_real_sample_ingests_cleanly_and_passes_dq(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pipeline, "sources_for", lambda _name: (C, R))
    respx.get(C.url).respond(
        200, content=_zip(FIXTURES / "complaints_sample.txt", tmp_path / "c.zip")
    )
    respx.get(R.url).respond(200, content=_zip(FIXTURES / "recalls_sample.txt", tmp_path / "r.zip"))
    settings = Settings(_env_file=None, data_dir=tmp_path / "data")  # type: ignore[call-arg]

    with httpx.Client() as client:
        reports, con = pipeline.run_ingest(settings, "dev", client)

    stats = {r.source.name: r.stats for r in reports}
    assert stats["C_SAMPLE"].rows_loaded == 2000
    assert stats["C_SAMPLE"].rows_rejected == 0
    assert stats["C_SAMPLE"].rows_cp1252 == 0  # current NHTSA files are UTF-8
    assert stats["R_SAMPLE"].rows_loaded == 200

    complaints = db.summarize(con, "complaints")
    assert complaints.row_count == 2000
    assert (
        complaints.distinct_keys == 1380
    )  # rows are per component: never count rows as complaints

    failed = [r for r in run_checks(con) if not r.passed]
    assert failed == []
