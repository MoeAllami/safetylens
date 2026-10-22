from pathlib import Path

import pytest
import respx
from builders import complaint_line, recall_line, write_zip
from typer.testing import CliRunner

from safetylens.cli import app
from safetylens.ingest import pipeline
from safetylens.ingest.sources import DEV_SOURCES, FULL_SOURCES, Source, sources_for

runner = CliRunner()
C = Source("C_TEST", "complaints", "https://example.test/C_TEST.zip")
R = Source("R_TEST", "recalls", "https://example.test/R_TEST.zip")


def test_dq_without_database_fails_with_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SAFETYLENS_DATA_DIR", str(tmp_path / "nothing"))
    result = runner.invoke(app, ["dq"])
    assert result.exit_code == 1
    assert "make data-dev" in result.output


@respx.mock
def test_ingest_then_dq_pass_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAFETYLENS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(pipeline, "sources_for", lambda _name: (C, R))
    c = write_zip(tmp_path / "c.zip", "C.txt", [complaint_line("1"), complaint_line("2")])
    r = write_zip(tmp_path / "r.zip", "R.txt", [recall_line("22V1")])
    respx.get(C.url).respond(200, content=c.read_bytes())
    respx.get(R.url).respond(200, content=r.read_bytes())

    ingest = runner.invoke(app, ["ingest", "--slice", "dev"])
    assert ingest.exit_code == 0, ingest.output
    assert "complaints_raw: 2 rows, 2 distinct keys" in ingest.output

    dq = runner.invoke(app, ["dq"])
    assert dq.exit_code == 0, dq.output
    assert "[FAIL]" not in dq.output


def test_slices_and_unknown_slice() -> None:
    assert sources_for("dev") == DEV_SOURCES
    assert sources_for("full") == FULL_SOURCES
    with pytest.raises(ValueError, match="unknown slice"):
        sources_for("everything")
