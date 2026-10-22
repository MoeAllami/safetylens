from pathlib import Path

import duckdb
import pytest
from builders import PII_MARKERS
from fastapi.testclient import TestClient
from web_helpers import GOOD, PLAN, web_db, web_engine

from safetylens.answer.llm import FakeLLM
from safetylens.answer.models import QueryPlan, VehicleRef, WriterOutput
from safetylens.web.app import DISCLAIMER, create_app

HX = {"HX-Request": "true"}


@pytest.fixture
def con(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    return web_db(tmp_path)


def client(con: duckdb.DuckDBPyConnection, llm: FakeLLM | None = None) -> TestClient:
    return TestClient(create_app(con, web_engine(con, llm or FakeLLM())))


def assert_no_pii(html: str) -> None:
    for marker in PII_MARKERS.values():
        if len(marker) > 2:  # "SD" (dealer state) is too short to search for
            assert marker not in html


def test_index_has_form_examples_and_disclaimer(con: duckdb.DuckDBPyConnection) -> None:
    page = client(con).get("/")
    assert page.status_code == 200
    assert 'hx-post="/ask"' in page.text and DISCLAIMER in page.text
    assert "/static/htmx.min.js" in page.text


def test_static_assets_are_served_locally(con: duckdb.DuckDBPyConnection) -> None:
    c = client(con)
    for name in ("htmx.min.js", "pico.min.css", "vega-embed.min.js", "app.js"):
        assert c.get(f"/static/{name}").status_code == 200, name


def test_answer_partial_links_citations_and_shows_sql_tables(
    con: duckdb.DuckDBPyConnection,
) -> None:
    llm = FakeLLM().script("planner", PLAN).script("writer", GOOD)
    page = client(con, llm).post("/ask", data={"question": "F-150 brakes?"}, headers=HX)
    assert page.status_code == 200
    assert 'data-status="answered"' in page.text
    assert '<a href="/complaint/11000001" class="cite">[11000001]</a>' in page.text
    assert "Most reported components" in page.text and 'class="chart"' in page.text
    assert "<html" not in page.text  # a partial, not a whole page
    assert_no_pii(page.text)


def test_without_htmx_the_whole_page_comes_back(con: duckdb.DuckDBPyConnection) -> None:
    llm = FakeLLM().script("planner", PLAN).script("writer", GOOD)
    page = client(con, llm).post("/ask", data={"question": "F-150 brakes?"})
    assert "<html" in page.text and DISCLAIMER in page.text and "/complaint/11000001" in page.text


def test_model_text_is_escaped(con: duckdb.DuckDBPyConnection) -> None:
    sneaky = WriterOutput(
        answer_markdown="<b onclick='x()'>owners</b> report brake failure [11000001].",
        citations=["11000001"],
    )
    llm = FakeLLM().script("planner", PLAN).script("writer", sneaky)
    page = client(con, llm).post("/ask", data={"question": "q"}, headers=HX)
    assert "<b onclick" not in page.text and "&lt;b onclick=" in page.text


def test_refusal_and_clarify_render(con: duckdb.DuckDBPyConnection) -> None:
    refused = FakeLLM().script("planner", QueryPlan(intent="out_of_scope", reason="verdict"))
    page = client(con, refused).post("/ask", data={"question": "Is it safe?"}, headers=HX)
    assert 'data-status="refused"' in page.text and "whether a vehicle is safe" in page.text
    assert "<table" not in page.text

    unknown = PLAN.model_copy(update={"vehicle": VehicleRef(make="Ford", model="Zephyrine")})
    page = client(con, FakeLLM().script("planner", unknown)).post(
        "/ask", data={"question": "q"}, headers=HX
    )
    assert 'data-status="clarify"' in page.text and "Which vehicle did you mean?" in page.text


@pytest.mark.parametrize("question", ["", "   ", "x" * 501])
def test_bad_question_is_rejected_without_calling_the_engine(
    con: duckdb.DuckDBPyConnection, question: str
) -> None:
    llm = FakeLLM()
    page = client(con, llm).post("/ask", data={"question": question}, headers=HX)
    assert page.status_code == 422 and llm.calls == []


def test_complaint_page_shows_record_and_nhtsa_link(con: duckdb.DuckDBPyConnection) -> None:
    page = client(con).get("/complaint/11000001")
    assert page.status_code == 200
    assert "THE BRAKES FAILED AND THE PEDAL WENT TO THE FLOOR" in page.text
    assert "https://api.nhtsa.gov/complaints/odinumber?odinumber=11000001" in page.text
    assert DISCLAIMER in page.text
    assert_no_pii(page.text)


@pytest.mark.parametrize("path", ["/complaint/99999999", "/complaint/abc", "/complaint/1' OR '1"])
def test_unknown_or_malformed_complaint_is_404(con: duckdb.DuckDBPyConnection, path: str) -> None:
    assert client(con).get(path).status_code == 404


def test_recall_page_accepts_lowercase_and_links_out(con: duckdb.DuckDBPyConnection) -> None:
    page = client(con).get("/recall/22v123000")
    assert page.status_code == 200
    assert "BRAKE LINE MAY LEAK" in page.text or "Recall 22V123000" in page.text
    assert "https://www.nhtsa.gov/recalls?nhtsaId=22V123000" in page.text
    assert "/vehicle/FORD/F-150/2022" in page.text
    assert client(con).get("/recall/22V999999").status_code == 404
    assert client(con).get("/recall/not-a-campaign").status_code == 404


def test_vehicle_page_shows_counts_charts_and_recalls(con: duckdb.DuckDBPyConnection) -> None:
    page = client(con).get("/vehicle/Ford/F150/2022")
    assert page.status_code == 200
    assert "3 distinct complaints" in page.text
    assert 'class="chart"' in page.text and "/recall/22V123000" in page.text


def test_unknown_vehicle_page_is_404_with_suggestions(con: duckdb.DuckDBPyConnection) -> None:
    page = client(con).get("/vehicle/Ford/Zephyrine/2022")
    assert page.status_code == 404 and "Which vehicle did you mean?" in page.text
