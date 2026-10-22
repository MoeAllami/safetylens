"""Phase 5: API failures become LLMError, per-stage timings, and the writer sees allowed numbers."""

import json
from pathlib import Path
from typing import Any

import anthropic
import duckdb
import httpx
import pytest
from conftest import engine, plan
from test_budget_pricing_llm import _client, _llm, _response
from test_pipeline import GOOD

from safetylens.answer.golden import GoldenReport, ItemResult
from safetylens.answer.golden_report import write_markdown
from safetylens.answer.llm import FakeLLM, LLMError


class FailingMessages:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def parse(self, **kwargs: Any) -> Any:
        raise self.exc


REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


@pytest.mark.parametrize(
    "exc",
    [
        anthropic.APIConnectionError(request=REQUEST),
        anthropic.BadRequestError(
            "credit balance is too low", response=httpx.Response(400, request=REQUEST), body=None
        ),
        anthropic.InternalServerError(
            "overloaded", response=httpx.Response(529, request=REQUEST), body=None
        ),
    ],
)
def test_api_failures_become_llm_errors(tmp_path: Path, exc: Exception) -> None:
    client = _client(_response(None))
    client.messages = client.beta.messages = FailingMessages(exc)
    with pytest.raises(LLMError, match="call failed"):
        _llm(tmp_path, client).structured("writer", "s", "u", GOOD.__class__, 50)


def test_answer_records_seconds_per_stage(answer_db: duckdb.DuckDBPyConnection) -> None:
    llm = FakeLLM().script("planner", plan()).script("writer", GOOD)
    answer = engine(answer_db, llm).ask("q")
    assert {"planner", "resolve", "sql", "retrieve", "writer_1", "validate"} <= set(answer.timings)
    assert "writer_2" not in answer.timings  # the first draft passed
    assert sum(answer.timings.values()) <= answer.latency_s


def test_writer_is_told_exactly_which_numbers_it_may_use(
    answer_db: duckdb.DuckDBPyConnection,
) -> None:
    llm = FakeLLM().script("planner", plan()).script("writer", GOOD)
    engine(answer_db, llm).ask("q")
    payload = json.loads(llm.calls[1][2])
    assert "4" in payload["allowed_numbers"] and "2022" in payload["allowed_numbers"]
    assert payload["allowed_numbers"] == sorted(payload["allowed_numbers"])


def _item(item_id: str, latency: float, timings: dict[str, float]) -> ItemResult:
    return ItemResult(
        id=item_id,
        intent_expected="top_components",
        status="answered",
        passed=True,
        failures=[],
        grounded=True,
        citations_valid=True,
        supported=1,
        judged=1,
        first_draft_ok=True,
        latency_s=latency,
        cost_usd=0.01,
        timings=timings,
    )


def test_report_shows_where_the_time_goes(tmp_path: Path) -> None:
    import datetime as dt

    items = [
        _item("g1", 5.0, {"planner": 1.0, "writer_1": 4.0}),
        _item("g2", 9.0, {"planner": 1.0, "writer_1": 4.0, "writer_2": 4.0}),
    ]
    report = GoldenReport(date=dt.date(2026, 1, 1), items=items, judge_cost_usd=0.0)
    stages = report.stage_latency()
    assert stages["planner"] == (1.0, 1.0)
    assert stages["writer_2"][0] == pytest.approx(2.0)  # skipped by g1, so it counts as 0 s
    text = write_markdown(report, tmp_path).read_text(encoding="utf-8")
    assert "## Where the time goes" in text and "| writer_1 | 4.00 | 4.00 |" in text
