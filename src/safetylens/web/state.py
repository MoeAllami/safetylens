"""Typed access to what create_app stores on app.state (Starlette types app.state as Any)."""

from typing import cast

from fastapi import Request
from fastapi.templating import Jinja2Templates


def templates(request: Request) -> Jinja2Templates:
    return cast(Jinja2Templates, request.app.state.templates)
