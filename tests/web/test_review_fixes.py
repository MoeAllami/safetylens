"""Phase 5 review fixes: vehicle URLs, year bounds, NULL flags, log content, chart quoting."""

from pathlib import Path

import duckdb
import pytest
import structlog
from builders import complaint_line, make_db, recall_line
from fastapi.testclient import TestClient
from web_helpers import web_db, web_engine

from safetylens.answer.llm import FakeLLM
from safetylens.web.app import create_app
from safetylens.web.charts import components_chart
from safetylens.web.records import recall


def client(con: duckdb.DuckDBPyConnection) -> TestClient:
    return TestClient(create_app(con, web_engine(con, FakeLLM())))


def test_plan_style_vehicle_url_redirects_to_the_year_first_one(tmp_path: Path) -> None:
    c = client(web_db(tmp_path))
    old = c.get("/vehicle/Ford/F-150/2022", follow_redirects=False)
    assert old.status_code == 301 and old.headers["location"] == "/vehicle/Ford/2022/F-150"
    assert c.get("/vehicle/Ford/2022/F-150").status_code == 200


def test_model_names_with_a_slash_route_and_link(tmp_path: Path) -> None:
    lines = [complaint_line("12000001", p5="E-350/E-450", narrative="BRAKES FAILED")]
    con = make_db(tmp_path, lines, [recall_line("23V100000", p4="E-350/E-450")])
    c = client(con)
    page = c.get("/recall/23V100000")
    assert 'href="/vehicle/FORD/2022/E-350/E-450"' in page.text
    vehicle = c.get("/vehicle/FORD/2022/E-350/E-450")
    assert vehicle.status_code == 200 and "1 distinct complaints" in vehicle.text


@pytest.mark.parametrize("year", ["0", "1900", "3000", "99999999999999999999"])
def test_out_of_range_years_are_a_404_page(tmp_path: Path, year: str) -> None:
    page = client(web_db(tmp_path)).get(f"/vehicle/Ford/{year}/F-150")
    assert page.status_code == 404 and "No model year" in page.text


def test_recall_with_null_flags_still_renders(tmp_path: Path) -> None:
    con = make_db(tmp_path, [complaint_line("12000001")], [recall_line("23V100001")])
    con.execute("UPDATE recalls SET do_not_drive = NULL, park_outside = NULL")
    record = recall(con, "23V100001")
    assert record is not None and record.do_not_drive is False and record.park_outside is False


def test_unmatched_paths_are_not_logged_raw(tmp_path: Path) -> None:
    with structlog.testing.capture_logs() as logs:
        client(web_db(tmp_path)).get("/some/typed/path?q=secret")
    routes = [e["route"] for e in logs if e.get("event") == "request"]
    assert routes == ["unmatched"]


def test_quotes_and_brackets_in_chart_values_stay_inside_the_attribute(tmp_path: Path) -> None:
    con = web_db(tmp_path)
    app = create_app(con, web_engine(con, FakeLLM()))
    spec = components_chart([{"component": 'SEAT "BELT" <b>', "complaints": 1, "vehicle": "v"}])
    html = str(app.state.templates.env.get_template("_chart.html").module.chart(spec))
    inside = html.split('data-spec="', 1)[1].rsplit('"', 1)[0]
    assert '"' not in inside and "<" not in inside  # nothing can end the attribute or open a tag
    assert "&#34;" in inside
