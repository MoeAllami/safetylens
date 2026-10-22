import datetime as dt
from pathlib import Path

import duckdb
from conftest import engine, plan
from test_pipeline import GOOD

from safetylens.answer.golden import (
    GoldenItem,
    GoldenReport,
    ItemResult,
    check_facts,
    load_golden,
    run_golden,
)
from safetylens.answer.golden_report import write_judge_review, write_markdown
from safetylens.answer.llm import FakeLLM
from safetylens.answer.models import JudgeVerdict, QueryPlan

YES = JudgeVerdict(supported=True, reason="same problem")
NO = JudgeVerdict(supported=False, reason="different problem")


def _item(**kw: object) -> GoldenItem:
    return GoldenItem.model_validate(
        {"id": "g01", "question": "q", "intent": "top_components", **kw}
    )


def test_answerable_item_passes_and_is_judged(answer_db: duckdb.DuckDBPyConnection) -> None:
    llm = FakeLLM().script("planner", plan()).script("writer", GOOD).script("judge", YES)
    item = _item(
        expected_facts={
            "resolved": "FORD F150",
            "distinct_complaints": 4,
            "top_component": "SERVICE BRAKES, HYDRAULIC",
        }
    )
    report = run_golden(engine(answer_db, llm), [item], today=dt.date(2026, 1, 2))
    (result,) = report.items
    assert result.passed, result.failures
    assert (result.grounded, result.citations_valid, result.supported, result.judged) == (
        True,
        True,
        1,
        1,
    )
    (verdict,) = result.verdicts
    assert (verdict.odino, verdict.supported, verdict.reason) == ("11000001", True, "same problem")
    assert verdict.claim.endswith("owners report brake failure [11000001].")
    judge_prompt = llm.calls[-1][2]
    assert "brake failure" in judge_prompt and "THE BRAKES FAILED" in judge_prompt


def test_wrong_facts_and_unsupported_citation_fail(answer_db: duckdb.DuckDBPyConnection) -> None:
    llm = FakeLLM().script("planner", plan()).script("writer", GOOD).script("judge", NO)
    item = _item(expected_facts={"distinct_complaints": 5, "peak_month": "2024-02"})
    (result,) = run_golden(engine(answer_db, llm), [item]).items
    assert not result.passed
    assert "distinct_complaints: want 5, got 4" in result.failures
    assert "citations supportive 0/1" in result.failures


def test_out_of_scope_item_needs_a_clean_refusal(answer_db: duckdb.DuckDBPyConnection) -> None:
    llm = FakeLLM().script("planner", QueryPlan(intent="out_of_scope"))
    item = _item(intent="out_of_scope", must_cite=False)
    (result,) = run_golden(engine(answer_db, llm), [item]).items
    assert result.passed and result.grounded is None


def test_check_facts_on_recalls_and_status(answer_db: duckdb.DuckDBPyConnection) -> None:
    from safetylens.answer.models import WriterOutput

    writer = WriterOutput(answer_markdown="1 recall [22V123000].", citations=["22V123000"])
    llm = FakeLLM().script("planner", plan("recalls")).script("writer", writer)
    answer = engine(answer_db, llm).ask("q")
    item = _item(
        intent="recalls",
        expected_facts={
            "campaign_in_results": "22V123000",
            "campaigns_total": 1,
            "status": "answered",
            "bogus": 1,
        },
    )
    assert check_facts(item, answer) == ["unknown expected fact 'bogus'"]


def _result(passed: bool, intent: str = "top_components", supported: int = 1) -> ItemResult:
    return ItemResult(
        id="x",
        intent_expected=intent,
        status="answered",
        passed=passed,
        failures=[],
        grounded=True,  # type: ignore[arg-type]
        citations_valid=True,
        supported=supported,
        judged=1,
        first_draft_ok=True,
        latency_s=2.0,
        cost_usd=0.02,
    )


def test_report_gates_and_markdown(tmp_path: Path) -> None:
    ok = GoldenReport(
        date=dt.date(2026, 1, 2),
        items=[_result(True)] * 9 + [_result(True, "out_of_scope")],
        judge_cost_usd=0.01,
    )
    assert ok.passed() and ok.metrics()["mean_cost_usd"] == 0.02
    weak = GoldenReport(
        date=dt.date(2026, 1, 2), items=[_result(True, supported=0)] * 2, judge_cost_usd=0.0
    )
    assert not weak.passed()  # citations_supportive 0%
    text = write_markdown(ok, tmp_path).read_text(encoding="utf-8")
    assert (
        "golden_pass           100%" in text and "| x | top_components | answered | pass |" in text
    )


def test_load_golden(tmp_path: Path) -> None:
    path = tmp_path / "g.yaml"
    path.write_text("items:\n  - {id: g01, question: q, intent: recalls}\n", encoding="utf-8")
    assert load_golden(path)[0].intent == "recalls"


def test_judge_review_file_lists_every_verdict(
    answer_db: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    llm = FakeLLM().script("planner", plan()).script("writer", GOOD).script("judge", NO)
    report = run_golden(engine(answer_db, llm), [_item()], today=dt.date(2026, 1, 2))
    text = write_judge_review(report, tmp_path / "eval").read_text(encoding="utf-8")
    assert "## g01 [11000001] NOT SUPPORTED" in text
    assert "- judge: different problem" in text
    assert "THE BRAKES FAILED" in text


def test_report_lists_rejected_first_drafts(
    answer_db: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    from test_pipeline import BAD

    llm = FakeLLM().script("planner", plan()).script("writer", BAD, GOOD).script("judge", YES)
    report = run_golden(engine(answer_db, llm), [_item()], today=dt.date(2026, 1, 2))
    text = write_markdown(report, tmp_path).read_text(encoding="utf-8")
    assert "## First drafts the validator rejected" in text
    assert "- g01: numbers not in the SQL results: 999" in text
