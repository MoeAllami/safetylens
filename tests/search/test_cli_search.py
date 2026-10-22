from pathlib import Path

import pytest
from builders import make_search_db
from typer.testing import CliRunner

from safetylens.cli import app
from safetylens.ingest.pipeline import DB_NAME
from safetylens.search import embed
from safetylens.search.embed import Embedder, HashingEmbedder

runner = CliRunner()


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SAFETYLENS_DATA_DIR", str(data))

    def fake(_name: str, _device: str, _batch: int) -> Embedder:
        return HashingEmbedder()

    monkeypatch.setattr(embed, "default_embedder", fake)
    make_search_db(tmp_path, db_path=data / DB_NAME).close()
    return data


def test_index_command_reports_progress(data_dir: Path) -> None:
    result = runner.invoke(app, ["index"])
    assert result.exit_code == 0, result.output
    assert "bm25 index: built" in result.output
    assert "embeddings: 0 new, 5 already current" in result.output


def test_search_command_prints_ranked_hits(data_dir: Path) -> None:
    args = ["search", "transmission slams", "--make", "FORD", "--model", "F-150", "--year", "2022"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert " 1. [3]" in result.output
    assert "TRANSMISSION SLAMS INTO GEAR" in result.output


def test_search_command_bm25_and_no_hits(data_dir: Path) -> None:
    args = ["search", "sunroof", "--make", "FORD", "--model", "F-150", "--method", "bm25"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert "no matching complaints" in result.output


def test_eval_retrieval_command_writes_report_and_gates(data_dir: Path, tmp_path: Path) -> None:
    labels = tmp_path / "labels.yaml"
    labels.write_text(
        "queries:\n"
        "  - {id: q1, make: FORD, model: F-150, year: 2022, query: transmission slams,"
        " relevant: ['3'], not_relevant: ['4']}\n",
        encoding="utf-8",
    )
    reports = tmp_path / "reports"
    result = runner.invoke(
        app, ["eval-retrieval", "--labels", str(labels), "--report-dir", str(reports)]
    )
    assert result.exit_code == 1  # every method scores 1.0, so hybrid does not beat the others
    assert "FAIL" in result.output
    assert len(list(reports.glob("retrieval-*.md"))) == 1


def test_index_without_database_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAFETYLENS_DATA_DIR", str(tmp_path / "missing"))
    monkeypatch.setattr(embed, "default_embedder", lambda *_: HashingEmbedder())
    result = runner.invoke(app, ["index"])
    assert result.exit_code == 1
