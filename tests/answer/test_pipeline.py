import json

import duckdb
import pytest
from conftest import engine, plan

from safetylens.answer.budget import BudgetExceeded
from safetylens.answer.llm import FakeLLM, LLMError, LLMRefusal
from safetylens.answer.models import QueryPlan, WriterOutput
from safetylens.answer.template import ERROR, REFUSAL

GOOD = WriterOutput(
    answer_markdown="The 2022 F-150 has 4 complaints; owners report brake failure [11000001].",
    citations=["11000001"],
)
BAD = WriterOutput(
    answer_markdown="999 owners report brake failure [11000001].", citations=["11000001"]
)


def test_happy_path_answers_with_citations(answer_db: duckdb.DuckDBPyConnection) -> None:
    llm = FakeLLM().script("planner", plan()).script("writer", GOOD)
    answer = engine(answer_db, llm).ask("brake complaints for 2022 F-150?")
    assert answer.status == "answered"
    assert answer.citations == ["11000001"]
    assert answer.first_draft_errors == [] and answer.writer_calls == 1
    assert answer.cost_usd == 0.002  # two fake calls
    payload = json.loads(llm.calls[1][2])
    assert payload["sql_results"]["complaint_count"][0]["complaints"] == 4
    assert {c["odino"] for c in payload["complaints"]} <= {
        "11000001",
        "11000002",
        "11000003",
        "11000004",
    }


def test_rejected_draft_is_retried_with_the_errors(answer_db: duckdb.DuckDBPyConnection) -> None:
    llm = FakeLLM().script("planner", plan()).script("writer", BAD, GOOD)
    answer = engine(answer_db, llm).ask("q")
    assert answer.status == "answered" and answer.writer_calls == 2
    assert answer.first_draft_errors[0].startswith("numbers not in the SQL results: 999")
    assert "rejected by the validator" in llm.calls[2][2]


def test_two_bad_drafts_fall_back_to_a_valid_template(answer_db: duckdb.DuckDBPyConnection) -> None:
    llm = FakeLLM().script("planner", plan()).script("writer", BAD, BAD)
    answer = engine(answer_db, llm).ask("q")
    assert answer.status == "fallback_template"
    assert "4 distinct complaints" in answer.text
    assert answer.citations and all(c in answer.text for c in answer.citations)


def test_out_of_scope_is_refused_without_writing(answer_db: duckdb.DuckDBPyConnection) -> None:
    llm = FakeLLM().script("planner", QueryPlan(intent="out_of_scope", reason="safety verdict"))
    answer = engine(answer_db, llm).ask("Is the F-150 safe?")
    assert (answer.status, answer.text, answer.citations) == ("refused", REFUSAL, [])
    assert [c[0] for c in llm.calls] == ["planner"]


def test_unknown_vehicle_asks_for_clarification(answer_db: duckdb.DuckDBPyConnection) -> None:
    llm = FakeLLM().script("planner", plan(model="Mustang"))
    answer = engine(answer_db, llm).ask("q")
    assert answer.status == "clarify" and answer.text.startswith("Which vehicle did you mean?")


def test_budget_and_refusals_never_crash(answer_db: duckdb.DuckDBPyConnection) -> None:
    no_budget = engine(answer_db, FakeLLM().script("planner", BudgetExceeded("cap"))).ask("q")
    assert no_budget.status == "budget_exceeded"
    planner_refused = engine(answer_db, FakeLLM().script("planner", LLMRefusal("x"))).ask("q")
    assert planner_refused.status == "refused"
    writer_refused = engine(
        answer_db, FakeLLM().script("planner", plan()).script("writer", LLMRefusal("x"))
    ).ask("q")
    assert writer_refused.status == "fallback_template"


def test_recalls_cite_campaigns_without_retrieval(answer_db: duckdb.DuckDBPyConnection) -> None:
    writer = WriterOutput(
        answer_markdown="1 recall covers it [22V123000].", citations=["22V123000"]
    )
    llm = FakeLLM().script("planner", plan("recalls")).script("writer", writer)
    answer = engine(answer_db, llm).ask("recalls?")
    assert answer.status == "answered" and answer.evidence == []


def test_compare_resolves_two_vehicles(answer_db: duckdb.DuckDBPyConnection) -> None:
    p = plan("compare").model_copy(update={"compare_vehicle": plan(model="F150").vehicle})
    llm = FakeLLM().script("planner", p).script("writer", GOOD)
    answer = engine(answer_db, llm).ask("compare")
    assert answer.compute is not None and len(answer.compute.vehicles) == 2


def test_fallback_template_uses_no_llm_text_and_is_validated(
    answer_db: duckdb.DuckDBPyConnection,
) -> None:
    sneaky = plan(search_text="twelve owners died in fires", component_system="SERVICE BRAKES")
    llm = FakeLLM().script("planner", sneaky).script("writer", BAD, BAD)
    answer = engine(answer_db, llm).ask("q")
    assert answer.status == "fallback_template"
    assert "twelve" not in answer.text and "fires" not in answer.text
    assert "Example reports describing service brakes:" in answer.text


def test_template_that_fails_validation_becomes_an_error(
    answer_db: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    from safetylens.answer import pipeline

    monkeypatch.setattr(pipeline, "template_answer", lambda *_: ("999 complaints.", []))
    llm = FakeLLM().script("planner", plan()).script("writer", BAD, BAD)
    answer = engine(answer_db, llm).ask("q")
    assert (answer.status, answer.text, answer.citations) == ("error", ERROR, [])
    assert answer.validation_errors[0].startswith("numbers not in the SQL results: 999")


def test_planner_error_is_not_dressed_up_as_a_safety_refusal(
    answer_db: duckdb.DuckDBPyConnection,
) -> None:
    answer = engine(answer_db, FakeLLM().script("planner", LLMError("truncated"))).ask("q")
    assert (answer.status, answer.text) == ("error", ERROR)
