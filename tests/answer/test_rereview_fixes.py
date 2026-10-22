"""Tests for the Phase 4 re-review blocking items and the compare-fallback fix."""

from pathlib import Path

import duckdb
import pytest
from builders import complaint_line, make_db, recall_line
from conftest import engine, plan
from test_pipeline import BAD

from safetylens.answer.compute import allowed_numbers, compute
from safetylens.answer.llm import FakeLLM
from safetylens.answer.numbers import citations_in, numbers_from_values
from safetylens.answer.resolver import resolve
from safetylens.answer.template import template_answer
from safetylens.answer.validator import validate
from safetylens.search.embed import HashingEmbedder
from safetylens.search.index import build_fts, embed_docs

ALLOWED = {"4", "2022", "150"}


@pytest.mark.parametrize(
    "text",
    [
        "See recall 23V999000 for details.",
        "A recall (23V999000) covers it.",
        "Recalls [22V123000, 23V999000] apply.",
        "Lowercase recall 23v999000 too.",
    ],
)
def test_unbracketed_campaign_ids_are_checked(
    answer_db: duckdb.DuckDBPyConnection, text: str
) -> None:
    assert "23V999000" in citations_in(text)
    errors = validate(answer_db, text, ["23V999000"], ALLOWED, {"22V123000"})
    assert any("23V999000" in e for e in errors)


def test_digits_with_units_from_sql_are_allowed() -> None:
    found = numbers_from_values([{"component": "ELECTRICAL SYSTEM:12V/24V/48V BATTERY:CABLES"}])
    assert {"12", "24", "48"} <= found


COMPONENT = "ELECTRICAL SYSTEM:12V/24V/48V BATTERY:CABLES"


@pytest.fixture
def battery_db(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    lines = [
        complaint_line("12000001", compdesc=COMPONENT, narrative="BATTERY DIED"),
        complaint_line("12000002", compdesc=COMPONENT, narrative="BATTERY CABLE MELTED"),
    ]
    recall = recall_line("24V500000", p7=COMPONENT)
    con = make_db(tmp_path, lines, [recall])
    build_fts(con)
    embed_docs(con, HashingEmbedder())
    return con


@pytest.mark.parametrize("intent", ["top_components", "recalls"])
def test_template_with_digit_bearing_component_passes_validation(
    battery_db: duckdb.DuckDBPyConnection, intent: str
) -> None:
    p = plan(intent)
    vehicle = resolve(battery_db, p.vehicle).vehicle  # type: ignore[arg-type]
    assert vehicle is not None
    result = compute(battery_db, p, [vehicle])
    text, cites = template_answer(result, [], "")
    assert "12V/24V/48V" in text
    assert validate(battery_db, text, cites, allowed_numbers(result, p), {"24V500000"}) == []


def test_compare_fallback_cites_reports_from_both_vehicles(tmp_path: Path) -> None:
    lines = [complaint_line(f"1300000{i}", narrative="BRAKES FAILED") for i in range(1, 4)]
    lines += [
        complaint_line(f"1400000{i}", narrative="BRAKES FAILED", p4="TOYOTA", p5="CAMRY")
        for i in range(1, 4)
    ]
    con = make_db(tmp_path, lines, [recall_line()])
    build_fts(con)
    embed_docs(con, HashingEmbedder())
    camry = plan(model="Camry").vehicle
    assert camry is not None
    camry = camry.model_copy(update={"make": "Toyota"})
    p = plan("compare").model_copy(update={"compare_vehicle": camry})
    answer = engine(con, FakeLLM().script("planner", p).script("writer", BAD, BAD)).ask("q")
    assert answer.status == "fallback_template"
    prefixes = {c[:4] for c in answer.citations}
    assert prefixes == {"1300", "1400"}  # both vehicles are represented
