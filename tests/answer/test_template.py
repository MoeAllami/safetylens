import duckdb
from conftest import plan

from safetylens.answer.compute import allowed_numbers, compute
from safetylens.answer.models import Evidence
from safetylens.answer.numbers import numbers_in
from safetylens.answer.resolver import resolve
from safetylens.answer.template import template_answer
from safetylens.answer.validator import validate

EVIDENCE = [Evidence(odino="11000001", received_date=None, components=[], narrative="x")]


def _render(con: duckdb.DuckDBPyConnection, intent: str) -> tuple[str, list[str], set[str]]:
    p = plan(intent)
    vehicle = resolve(con, p.vehicle).vehicle  # type: ignore[arg-type]
    assert vehicle is not None
    vehicles = [vehicle, vehicle] if intent == "compare" else [vehicle]
    result = compute(con, p, vehicles)
    text, cites = template_answer(result, EVIDENCE)
    return text, cites, allowed_numbers(result, p)


def test_every_template_passes_the_validator(answer_db: duckdb.DuckDBPyConnection) -> None:
    for intent in ("top_components", "trend", "recalls", "examples", "compare"):
        text, cites, numbers = _render(answer_db, intent)
        allowed_ids = {"11000001", "22V123000"}
        assert validate(answer_db, text, cites, numbers, allowed_ids) == [], intent
        assert numbers_in(text) <= numbers


def test_trend_and_recall_templates_say_the_right_thing(
    answer_db: duckdb.DuckDBPyConnection,
) -> None:
    trend, _, _ = _render(answer_db, "trend")
    assert "busiest month was 2024-01 with 4 complaints" in trend
    recalls, cites, _ = _render(answer_db, "recalls")
    assert cites == ["22V123000"] and "[22V123000] SERVICE BRAKES, HYDRAULIC" in recalls
