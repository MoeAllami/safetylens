"""Golden-output tests for every SQL template (Phase 2 gate).

Expected values were worked out by hand from the rows below, not copied from the code's output.
Traps on purpose: ODINO 1 lists two components (COUNT(*) would say 6 complaints, the truth is 5),
ODINO 4 also names a tire (non-vehicle row, must be ignored), ODINO 5 has model year 9999, ODINO 8
spells the model "F150", and recall 22V100000 repeats once per manufacturer part.
"""

import datetime as dt
from pathlib import Path

import duckdb
import pytest
from builders import complaint_line as c
from builders import make_db
from builders import recall_line as r

from safetylens.analytics import templates as t
from safetylens.dq import run_checks

COMPLAINTS = [
    c("1", "SERVICE BRAKES, HYDRAULIC", p7="Y", p10="2", p17="20240115", p18="0"),
    c("1", "STEERING", p7="Y", p10="2", p17="20240115", p18="0"),
    c("2", "SERVICE BRAKES, HYDRAULIC", p9="Y", p11="1", p17="20240302"),
    c("3", "SERVICE BRAKES", p6="2021", p17="20240320"),
    c("4", "TIRES", p17="20240130"),
    c("4", "TIRES", p46="T", p4="GOODYEAR", p5="G-METRIC", p6="9999", p10="5", p17="20240130"),
    c("5", "ENGINE", p6="9999", p17="20240210"),
    c("6", "ENGINE", p5="F-150 HYBRID", p17="20240115"),
    c("7", "ENGINE", p4="TOYOTA", p5="CAMRY", p17="20240115"),
    c("8", "ENGINE", p5="F150", p17="20240405"),
]
RECALLS = [
    r("22V100000", p7="SERVICE BRAKES, HYDRAULIC", p16="20220501", p12="1000"),
    r("22V100000", p7="SERVICE BRAKES, HYDRAULIC", p16="20220501", p12="1000", p25="CALIPER"),
    r("22V100000", p5="2021", p7="SERVICE BRAKES, HYDRAULIC", p16="20220501", p12="1000"),
    r("23V200000", p7="STEERING", p16="20230201", p12="500", p28="Yes"),
    r("21V300000", p5="2020", p7="ENGINE", p16="20210101"),
    r("22T400000", p11="T", p7="TIRES", p16="20220601"),
    r("24V500000", p4="F150", p7="ELECTRICAL SYSTEM", p16="20240301"),
]

F150_2021_22 = t.VehicleFilter(make="ford", model="F-150", year_from=2021, year_to=2022)


@pytest.fixture
def con(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    return make_db(tmp_path, COMPLAINTS, RECALLS)


def test_dq_passes_on_golden_data(con: duckdb.DuckDBPyConnection) -> None:
    assert [r.name for r in run_checks(con) if not r.passed] == []


def test_complaint_count(con: duckdb.DuckDBPyConnection) -> None:
    assert t.complaint_count(con, F150_2021_22) == 5  # ODINOs 1, 2, 3, 4, 8
    no_years = F150_2021_22.model_copy(update={"year_from": None, "year_to": None})
    assert t.complaint_count(con, no_years) == 6  # + ODINO 5 (year unknown)


def test_top_components(con: duckdb.DuckDBPyConnection) -> None:
    rows = [
        (x.component_system, x.component, x.complaints, x.crashes, x.fires)
        for x in t.top_components(con, F150_2021_22)
    ]
    assert rows == [
        ("SERVICE BRAKES", "SERVICE BRAKES, HYDRAULIC", 2, 1, 1),
        ("ENGINE", "ENGINE", 1, 0, 0),
        ("SERVICE BRAKES", "SERVICE BRAKES", 1, 0, 0),
        ("STEERING", "STEERING", 1, 1, 0),
        ("TIRES", "TIRES", 1, 0, 0),
    ]


def test_top_components_filters_and_limit(con: duckdb.DuckDBPyConnection) -> None:
    brakes = F150_2021_22.model_copy(update={"component_system": "SERVICE BRAKES"})
    assert [(x.component, x.complaints) for x in t.top_components(con, brakes)] == [
        ("SERVICE BRAKES, HYDRAULIC", 2),
        ("SERVICE BRAKES", 1),
    ]
    assert len(t.top_components(con, F150_2021_22, limit=2)) == 2


def test_monthly_trend_fills_empty_months(con: duckdb.DuckDBPyConnection) -> None:
    rows = [(m.month, m.complaints) for m in t.monthly_trend(con, F150_2021_22)]
    assert rows == [
        (dt.date(2024, 1, 1), 2),  # ODINOs 1, 4
        (dt.date(2024, 2, 1), 0),  # only ODINO 5, whose model year is unknown
        (dt.date(2024, 3, 1), 2),  # ODINOs 2, 3
        (dt.date(2024, 4, 1), 1),  # ODINO 8
    ]


def test_monthly_trend_spans_requested_range(con: duckdb.DuckDBPyConnection) -> None:
    f = F150_2021_22.model_copy(
        update={"received_from": dt.date(2023, 12, 1), "received_to": dt.date(2024, 5, 31)}
    )
    assert [m.complaints for m in t.monthly_trend(con, f)] == [0, 2, 0, 2, 1, 0]
    steering = F150_2021_22.model_copy(update={"component_system": "STEERING"})
    assert [(m.month, m.complaints) for m in t.monthly_trend(con, steering)] == [
        (dt.date(2024, 1, 1), 1)
    ]


def test_severity_counts_each_complaint_once(con: duckdb.DuckDBPyConnection) -> None:
    s = t.severity(con, F150_2021_22)
    # injured is 2, not 4: ODINO 1 has two component rows; the tire row's 5 is excluded.
    assert s == t.Severity(
        complaints=5, with_crash=1, with_fire=1, with_injury=1, with_death=1, injured=2, deaths=1
    )


def test_recalls_by_vehicle(con: duckdb.DuckDBPyConnection) -> None:
    f = t.VehicleFilter(make="FORD", model="F-150", year_from=2022, year_to=2022)
    rows = t.recalls_by_vehicle(con, f)
    assert [(x.campno, x.report_date, x.do_not_drive) for x in rows] == [
        ("24V500000", dt.date(2024, 3, 1), False),  # model spelled "F150"
        ("23V200000", dt.date(2023, 2, 1), True),
        ("22V100000", dt.date(2022, 5, 1), False),  # part rows collapse to one campaign
    ]
    assert {x.campaigns_total for x in rows} == {3}  # tire recall 22T400000 excluded
    assert rows[2].components == ["SERVICE BRAKES, HYDRAULIC"]
    assert rows[2].potentially_affected == 1000


def test_recalls_filters(con: duckdb.DuckDBPyConnection) -> None:
    brakes = t.VehicleFilter(
        make="FORD", model="F-150", year_from=2022, year_to=2022, component_system="SERVICE BRAKES"
    )
    assert [(x.campno, x.campaigns_total) for x in t.recalls_by_vehicle(con, brakes)] == [
        ("22V100000", 1)
    ]
    wide = t.VehicleFilter(make="FORD", model="F-150", year_from=2020, year_to=2022)
    assert len(t.recalls_by_vehicle(con, wide)) == 4  # + 21V300000 (2020)


def test_unknown_vehicle_returns_empty_results(con: duckdb.DuckDBPyConnection) -> None:
    f = t.VehicleFilter(make="NOPE", model="NOTHING")
    assert t.complaint_count(con, f) == 0
    assert t.top_components(con, f) == []
    assert t.monthly_trend(con, f) == []
    assert t.severity(con, f).complaints == 0
    assert t.recalls_by_vehicle(con, f) == []


def test_python_model_key_matches_sql(con: duckdb.DuckDBPyConnection) -> None:
    rows = con.execute("SELECT model, model_key FROM vehicle_models").fetchall()
    assert rows
    assert all(t.model_key(model) == key for model, key in rows)


def test_aliases_include_curated_and_self(con: duckdb.DuckDBPyConnection) -> None:
    rows = set(
        con.execute("SELECT make, alias_key, model_key, source FROM model_aliases").fetchall()
    )
    assert ("FORD", "F150", "F150", "self") in rows
    assert ("TESLA", "MODELY(ALLVARIANTS)", "MODELY", "curated") in rows


def test_component_systems_lookup(con: duckdb.DuckDBPyConnection) -> None:
    rows = dict(con.execute("SELECT component, component_system FROM component_systems").fetchall())
    assert rows["SERVICE BRAKES, HYDRAULIC"] == "SERVICE BRAKES"
    assert rows["ELECTRICAL SYSTEM"] == "ELECTRICAL SYSTEM"
