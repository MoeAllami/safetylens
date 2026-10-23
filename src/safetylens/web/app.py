"""The FastAPI app: a factory that takes the database and answer engine it should use.

Why a factory: tests and the browser test build the same app with a FakeLLM and a small test
database, while `safetylens serve` passes the real engine, loaded once so every request is warm.
"""

import threading
import time
import uuid
from collections.abc import Awaitable, Callable
from importlib.resources import files
from pathlib import Path

import duckdb
import structlog
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException

from safetylens.answer.pipeline import Engine
from safetylens.web import routes_ask, routes_records
from safetylens.web.records import complaint_url, recall_url

log = structlog.get_logger()
WEB_DIR = Path(str(files("safetylens.web")))
DISCLAIMER = (
    "Complaints are unverified consumer reports filed with NHTSA. Counts are not defect rates. "
    "Data: U.S. National Highway Traffic Safety Administration."
)


def create_app(con: duckdb.DuckDBPyConnection, engine: Engine) -> FastAPI:
    app = FastAPI(title="SafetyLens", docs_url=None, redoc_url=None)
    templates = Jinja2Templates(directory=WEB_DIR / "templates")
    templates.env.globals.update(
        disclaimer=DISCLAIMER,
        complaint_url=complaint_url,
        recall_url=recall_url,
        vehicle_path=routes_records.vehicle_path,
    )
    app.state.con = con
    app.state.engine = engine
    app.state.templates = templates
    # One DuckDB connection is not safe to share across threads: answers (which use the engine's
    # connection) run one at a time, and record pages read through their own cursor.
    app.state.ask_lock = threading.Lock()
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
    app.include_router(routes_ask.router)
    app.include_router(routes_records.router)

    @app.middleware("http")
    async def log_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Route, status and time only: never the question text or anything from a record.
        started = time.perf_counter()
        request.state.request_id = uuid.uuid4().hex[:8]
        response = await call_next(request)
        log.info(
            "request",
            request_id=request.state.request_id,
            method=request.method,
            route=getattr(request.scope.get("route"), "path", "unmatched"),
            status=response.status_code,
            seconds=round(time.perf_counter() - started, 3),
        )
        return response

    def error_page(request: Request, status: int, message: str) -> HTMLResponse:
        context = {"message": message, "request_id": getattr(request.state, "request_id", "")}
        name = "_message.html" if request.headers.get("HX-Request") else "error.html"
        return templates.TemplateResponse(request, name, context, status_code=status)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> HTMLResponse:
        message = "Page not found." if exc.status_code == 404 else "That request did not work."
        return error_page(request, exc.status_code, message)

    @app.exception_handler(RequestValidationError)
    async def bad_params(request: Request, exc: RequestValidationError) -> HTMLResponse:
        return error_page(request, 404, "Page not found.")

    @app.exception_handler(Exception)
    async def server_error(request: Request, exc: Exception) -> HTMLResponse:
        # The exception type only: its message could quote data, and tracebacks stay off pages.
        log.error(
            "server_error",
            request_id=getattr(request.state, "request_id", ""),
            error=type(exc).__name__,
        )
        return error_page(request, 500, "Something went wrong on our side. Please try again.")

    return app
