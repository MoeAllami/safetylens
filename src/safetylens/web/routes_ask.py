"""The question page and the HTMX answer partial.

Why a partial: HTMX posts the form and swaps only the answer block into the page, so the app
needs no JavaScript of its own. Without HTMX (no HX-Request header) the same route returns the
whole page with the answer in it.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from safetylens.answer.models import Answer
from safetylens.web.charts import charts_for
from safetylens.web.render import answer_html
from safetylens.web.state import templates

router = APIRouter()
MAX_QUESTION_CHARS = 500
EXAMPLES = [
    "What are the most common complaints for a 2022 Ford F-150?",
    "How have brake complaints for the 2021 Honda CR-V changed over time?",
    "Are there recalls for the 2020 Tesla Model 3?",
    "Compare complaints for the 2022 Toyota RAV4 and the 2022 Honda CR-V.",
]
# Which SQL tables an answer shows, and which of their columns (the rest are for the writer).
TABLES: dict[str, tuple[str, list[str]]] = {
    "complaint_count": ("Matching complaints", ["vehicle", "complaints"]),
    "top_components": (
        "Most reported components",
        ["vehicle", "component", "complaints", "crashes", "fires"],
    ),
    "severity": (
        "Severity",
        ["vehicle", "complaints", "with_crash", "with_fire", "with_injury", "with_death"],
    ),
    "recalls": ("Recall campaigns", ["vehicle", "campno", "report_date", "components"]),
}


def _tables(answer: Answer) -> list[dict[str, Any]]:
    if answer.compute is None:
        return []
    shown = []
    for name, (title, columns) in TABLES.items():
        rows = answer.compute.tables.get(name, [])
        if rows:
            shown.append({"title": title, "columns": columns, "rows": rows})
    return shown


def _context(answer: Answer) -> dict[str, Any]:
    return {
        "answer": answer,
        "answer_html": answer_html(answer.text, answer.citations),
        "tables": _tables(answer),
        "charts": charts_for(answer.compute.tables) if answer.compute else [],
    }


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates(request).TemplateResponse(request, "index.html", {"examples": EXAMPLES})


@router.post("/ask", response_class=HTMLResponse)
def ask(request: Request, question: Annotated[str, Form()] = "") -> HTMLResponse:
    question = question.strip()
    if not question or len(question) > MAX_QUESTION_CHARS:
        message = f"Please ask a question of 1 to {MAX_QUESTION_CHARS} characters."
        return templates(request).TemplateResponse(
            request, "_message.html", {"message": message}, status_code=422
        )
    with request.app.state.ask_lock:
        answer = request.app.state.engine.ask(question)
    context = _context(answer)
    if request.headers.get("HX-Request"):
        return templates(request).TemplateResponse(request, "_answer.html", context)
    return templates(request).TemplateResponse(
        request, "index.html", {"examples": EXAMPLES, "question": question, **context}
    )
