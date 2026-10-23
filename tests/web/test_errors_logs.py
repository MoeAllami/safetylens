"""Error pages never show tracebacks; logs redact anything that could carry text or PII."""

import io
import json
from pathlib import Path

import pytest
import structlog
from fastapi import Request
from fastapi.testclient import TestClient
from web_helpers import web_db, web_engine

from safetylens import logs
from safetylens.answer.llm import FakeLLM
from safetylens.web.app import DISCLAIMER, create_app


@pytest.fixture
def app_client(tmp_path: Path) -> TestClient:
    con = web_db(tmp_path)
    app = create_app(con, web_engine(con, FakeLLM()))

    @app.get("/boom")
    def boom(request: Request) -> None:
        raise RuntimeError("SECRET narrative text from a record")

    return TestClient(app, raise_server_exceptions=False)


def test_unknown_route_is_a_friendly_404(app_client: TestClient) -> None:
    page = app_client.get("/no/such/page")
    assert page.status_code == 404 and "Page not found." in page.text and DISCLAIMER in page.text


def test_bad_path_parameter_is_a_404_not_a_json_error(app_client: TestClient) -> None:
    page = app_client.get("/vehicle/Ford/F-150/not-a-year")
    assert page.status_code == 404 and "<html" in page.text


def test_server_error_page_hides_the_exception(app_client: TestClient) -> None:
    with structlog.testing.capture_logs() as captured:
        page = app_client.get("/boom")
    assert page.status_code == 500 and "Something went wrong" in page.text
    assert "SECRET" not in page.text and "Traceback" not in page.text
    assert "Request id:" in page.text
    errors = [e for e in captured if e["event"] == "server_error"]
    assert errors and errors[0]["error"] == "RuntimeError" and "SECRET" not in str(errors)


def test_htmx_errors_get_a_partial(app_client: TestClient) -> None:
    page = app_client.get("/no/such/page", headers={"HX-Request": "true"})
    assert page.status_code == 404 and "<html" not in page.text and "Page not found." in page.text


def test_forbidden_keys_are_redacted_before_rendering() -> None:
    out = io.StringIO()
    logs.configure(json_output=True)
    structlog.configure(logger_factory=structlog.PrintLoggerFactory(file=out))
    try:
        structlog.get_logger().info(
            "x",
            narrative="THE BRAKES FAILED",
            question="is it safe",
            VIN="1FT...",
            dealer_name="Bob",
            odino="11000001",
        )
    finally:
        structlog.reset_defaults()
    line = json.loads(out.getvalue())
    for key in ("narrative", "question", "VIN", "dealer_name"):
        assert line[key] == "[redacted]"
    assert line["odino"] == "11000001" and line["level"] == "info" and "timestamp" in line
