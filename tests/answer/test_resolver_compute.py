import duckdb
from conftest import plan

from safetylens.answer.compute import allowed_numbers, compute
from safetylens.answer.models import VehicleRef
from safetylens.answer.resolver import resolve


def _ref(make: str, model: str) -> VehicleRef:
    return VehicleRef(make=make, model=model, year_from=2022)


def test_resolve_exact_alias_fuzzy_and_years(answer_db: duckdb.DuckDBPyConnection) -> None:
    exact = resolve(answer_db, _ref("ford", "F-150"))
    fuzzy = resolve(answer_db, _ref("Ford", "F150 pickup"))
    assert exact.vehicle is not None and fuzzy.vehicle is not None
    assert (exact.vehicle.model_key, fuzzy.vehicle.model_key) == ("F150", "F150")
    assert (exact.vehicle.year_from, exact.vehicle.year_to) == (2022, 2022)  # one year fills both
    assert exact.vehicle.label == "2022 FORD F-150"


def test_resolve_asks_instead_of_guessing(answer_db: duckdb.DuckDBPyConnection) -> None:
    unknown_model = resolve(answer_db, _ref("Ford", "Mustang"))
    unknown_make = resolve(answer_db, _ref("Foo", "Bar"))
    assert unknown_model.status == "clarify"
    assert unknown_make.status == "clarify" and "No manufacturer" in unknown_make.options[0]


def test_compute_top_components_and_allowed_numbers(answer_db: duckdb.DuckDBPyConnection) -> None:
    p = plan()
    vehicle = resolve(answer_db, p.vehicle).vehicle  # type: ignore[arg-type]
    assert vehicle is not None
    result = compute(answer_db, p, [vehicle])
    assert result.tables["complaint_count"] == [{"vehicle": "2022 FORD F-150", "complaints": 4}]
    assert result.tables["top_components"][0]["component"] == "SERVICE BRAKES, HYDRAULIC"
    assert {"4", "2", "2022", "150"} <= allowed_numbers(result, p)


def test_compute_recalls_and_trend(answer_db: duckdb.DuckDBPyConnection) -> None:
    vehicle = resolve(answer_db, _ref("Ford", "F-150")).vehicle
    assert vehicle is not None
    recalls = compute(answer_db, plan("recalls"), [vehicle])
    assert [r["campno"] for r in recalls.tables["recalls"]] == ["22V123000"]
    trend = compute(answer_db, plan("trend"), [vehicle])
    assert trend.tables["monthly_trend"] == [
        {"vehicle": "2022 FORD F-150", "month": "2024-01-01", "complaints": 4}
    ]


def test_compute_ignores_unknown_or_injection_shaped_system(
    answer_db: duckdb.DuckDBPyConnection,
) -> None:
    vehicle = resolve(answer_db, _ref("Ford", "F-150")).vehicle
    assert vehicle is not None
    p = plan(component_system="BRAKES' OR '1'='1")
    result = compute(answer_db, p, [vehicle])
    assert "filters" not in result.tables
    assert result.tables["complaint_count"][0]["complaints"] == 4  # unfiltered, not hijacked
