from pathlib import Path
from typing import Any

import pytest
from builders import make_db, recall_line
from conftest import answer_lines, engine, plan
from test_pipeline import GOOD
from typer.testing import CliRunner

from safetylens.answer import runtime
from safetylens.answer.llm import FakeLLM
from safetylens.answer.models import JudgeVerdict, QueryPlan
from safetylens.cli import app
from safetylens.ingest.pipeline import DB_NAME
from safetylens.search.embed import HashingEmbedder
from safetylens.search.index import build_fts, embed_docs

runner = CliRunner()


@pytest.fixture
def fake_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeLLM:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SAFETYLENS_DATA_DIR", str(data))
    con = make_db(tmp_path, answer_lines(), [recall_line("22V123000")], db_path=data / DB_NAME)
    build_fts(con)
    embed_docs(con, HashingEmbedder())
    con.close()
    llm = FakeLLM()
    monkeypatch.setattr(runtime, "build_llm", lambda *_: llm)
    monkeypatch.setattr(runtime, "build_engine", lambda _s, con, llm_: engine(con, llm_))
    return llm


def test_ask_prints_answer_status_and_disclaimer(fake_runtime: FakeLLM) -> None:
    fake_runtime.script("planner", plan()).script("writer", GOOD)
    result = runner.invoke(app, ["ask", "brake complaints for 2022 F-150?"])
    assert result.exit_code == 0, result.output
    assert "owners report brake failure [11000001]" in result.output
    assert "[answered] citations: 11000001" in result.output
    assert "Counts are not defect rates." in result.output


def test_eval_runs_items_writes_report_and_gates(fake_runtime: FakeLLM, tmp_path: Path) -> None:
    fake_runtime.script("planner", plan(), QueryPlan(intent="out_of_scope"))
    fake_runtime.script("writer", GOOD).script("judge", JudgeVerdict(supported=True, reason="ok"))
    golden = tmp_path / "golden.yaml"
    golden.write_text(
        "items:\n"
        "  - {id: g01, question: q1, intent: top_components,\n"
        "     expected_facts: {distinct_complaints: 4}}\n"
        "  - {id: g02, question: q2, intent: out_of_scope, must_cite: false}\n"
        "  - {id: g03, question: q3, intent: trend}\n",
        encoding="utf-8",
    )
    reports = tmp_path / "reports"
    args: list[Any] = [
        "eval",
        "--golden",
        str(golden),
        "--report-dir",
        str(reports),
        "--ids",
        "g01,g02",
    ]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert "golden_pass           100%  (target >= 85%) of 2" in result.output
    assert "refusals              1/1" in result.output
    assert len(list(reports.glob("answers-*.md"))) == 1
    assert "judge verdicts for spot-checking (git-ignored)" in result.output
