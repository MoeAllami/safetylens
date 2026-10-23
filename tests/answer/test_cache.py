from dataclasses import replace
from pathlib import Path

import duckdb
import pytest
from conftest import engine, plan
from test_pipeline import BAD, GOOD

from safetylens.answer import prompts
from safetylens.answer.cache import AnswerCache, answer_version, cache_key, data_version
from safetylens.answer.llm import FakeLLM
from safetylens.answer.models import QueryPlan, ResolvedVehicle

F150 = ResolvedVehicle(make="FORD", model="F-150", model_key="F150", year_from=2022, year_to=2022)


def cached_engine(con: duckdb.DuckDBPyConnection, llm: FakeLLM, path: Path):  # type: ignore[no-untyped-def]
    return replace(engine(con, llm), cache=AnswerCache(path, "claude-sonnet-5-5:low"))


def test_same_plan_is_answered_once(answer_db: duckdb.DuckDBPyConnection, tmp_path: Path) -> None:
    llm = FakeLLM().script("planner", plan(), plan()).script("writer", GOOD)
    eng = cached_engine(answer_db, llm, tmp_path / "c.sqlite")
    first, second = eng.ask("brakes on a 2022 F-150?"), eng.ask("2022 Ford F150 brake problems")
    assert not first.cached and second.cached
    assert second.question == "2022 Ford F150 brake problems"
    assert (second.text, second.citations) == (first.text, first.citations)
    assert second.writer_calls == 0 and "cache" in second.timings
    assert second.cost_usd == pytest.approx(0.001)  # the planner call only


def test_different_filters_miss(answer_db: duckdb.DuckDBPyConnection, tmp_path: Path) -> None:
    other = plan("trend")  # same vehicle, different intent
    llm = FakeLLM().script("planner", plan(), other).script("writer", GOOD, GOOD)
    eng = cached_engine(answer_db, llm, tmp_path / "c.sqlite")
    eng.ask("a")
    assert not eng.ask("b").cached


def test_refusals_and_errors_are_never_cached(
    answer_db: duckdb.DuckDBPyConnection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from safetylens.answer import pipeline

    monkeypatch.setattr(pipeline, "template_answer", lambda *_: ("999 complaints.", []))
    oos = QueryPlan(intent="out_of_scope", reason="verdict")
    llm = FakeLLM().script("planner", oos, oos, plan(), plan()).script("writer", BAD, BAD, GOOD)
    eng = cached_engine(answer_db, llm, tmp_path / "c.sqlite")
    assert eng.ask("safe?").status == "refused" and not eng.ask("safe?").cached
    assert eng.ask("q").status == "error"
    retry = eng.ask("q")
    assert retry.status == "answered" and not retry.cached  # the error was not stored


def test_engine_without_cache_never_caches(answer_db: duckdb.DuckDBPyConnection) -> None:
    llm = FakeLLM().script("planner", plan(), plan()).script("writer", GOOD, GOOD)
    eng = engine(answer_db, llm)  # how the eval builds it
    eng.ask("a")
    assert not eng.ask("a").cached and [c[0] for c in llm.calls].count("writer") == 2


def test_key_depends_on_data_and_answer_version(answer_db: duckdb.DuckDBPyConnection) -> None:
    data = data_version(answer_db)
    base = cache_key(plan(), [F150], data, "v1")
    assert cache_key(plan(search_text="  Brakes   FAILED "), [F150], data, "v1") == base
    assert cache_key(plan(), [F150], data + "x", "v1") != base
    assert cache_key(plan(), [F150], data, "v2") != base
    assert cache_key(plan("trend"), [F150], data, "v1") != base
    later = F150.model_copy(update={"year_from": 2023, "year_to": 2023})
    assert cache_key(plan(), [later], data, "v1") != base


def test_answer_version_changes_with_prompts_and_writer(monkeypatch: pytest.MonkeyPatch) -> None:
    v = answer_version("claude-sonnet-5-5:low")
    assert answer_version("claude-sonnet-5-5:medium") != v
    monkeypatch.setattr(prompts, "WRITER", prompts.WRITER + " ")
    assert answer_version("claude-sonnet-5-5:low") != v


def test_rebuilt_data_changes_the_version(answer_db: duckdb.DuckDBPyConnection) -> None:
    before = data_version(answer_db)
    answer_db.execute("DELETE FROM complaint_docs WHERE odino = '11000004'")
    assert data_version(answer_db) != before


def test_clear_and_persistence(tmp_path: Path) -> None:
    from safetylens.answer.models import Answer

    path = tmp_path / "c.sqlite"
    cache = AnswerCache(path, "w")
    cache.put("k", Answer(question="q", status="answered", text="t"))
    cache.close()
    reopened = AnswerCache(path, "w")
    hit = reopened.get("k")
    assert hit is not None and hit.text == "t"
    assert reopened.clear() == 1 and reopened.get("k") is None
