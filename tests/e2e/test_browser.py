"""D11 + D15 in a real browser: ask -> answer -> citation -> record page -> NHTSA link.

Why FakeLLM here: the browser test checks the app's wiring (HTMX swap, links, vendored scripts,
disclaimer), not the model, so it is free, deterministic and needs no API key. The real models
are measured by `make eval`.
"""

import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn
from web_helpers import GOOD, PLAN, web_db, web_engine

from safetylens.answer.llm import FakeLLM
from safetylens.web.app import create_app

pytestmark = pytest.mark.e2e
playwright = pytest.importorskip("playwright.sync_api")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def app_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    con = web_db(tmp_path_factory.mktemp("e2e"))
    llm = FakeLLM().script("planner", PLAN).script("writer", GOOD)
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(create_app(con, web_engine(con, llm)), port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("test server did not start")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def test_question_to_record_to_nhtsa(page: "playwright.Page", app_url: str) -> None:
    expect = playwright.expect
    page.goto(app_url)
    expect(page.locator("#disclaimer")).to_contain_text("Counts are not defect rates")
    expect(page.locator("#disclaimer")).to_contain_text(
        "Data: U.S. National Highway Traffic Safety Administration"
    )

    page.fill("#question", "What are the most common complaints for a 2022 Ford F-150?")
    page.click("button[type=submit]")
    card = page.locator("#answer-card")
    expect(card).to_have_attribute("data-status", "answered")
    expect(card).to_contain_text("owners report brake failure")
    # The vendored Vega scripts drew the chart (canvas or svg inside the placeholder).
    expect(page.locator(".chart canvas, .chart svg").first).to_be_visible()
    assert page.url.rstrip("/") == app_url  # HTMX swapped the answer in; no navigation

    page.click("a.cite >> text=[11000001]")
    expect(page).to_have_url(f"{app_url}/complaint/11000001")
    expect(page.locator("h1")).to_have_text("Complaint 11000001")
    expect(page.locator(".narrative")).to_contain_text("THE BRAKES FAILED")
    expect(page.locator("#nhtsa-link")).to_have_attribute(
        "href", "https://api.nhtsa.gov/complaints/odinumber?odinumber=11000001"
    )
    expect(page.locator("#disclaimer")).to_contain_text("unverified consumer reports")


def test_recall_and_vehicle_pages(page: "playwright.Page", app_url: str) -> None:
    expect = playwright.expect
    page.goto(f"{app_url}/recall/22V123000")
    expect(page.locator("#nhtsa-link")).to_have_attribute(
        "href", "https://www.nhtsa.gov/recalls?nhtsaId=22V123000"
    )
    page.get_by_role("link", name="2022", exact=True).click()
    expect(page.locator("h1")).to_contain_text("F-150")
    expect(page.locator(".chart canvas, .chart svg").first).to_be_visible()
