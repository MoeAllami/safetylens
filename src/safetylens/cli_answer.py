"""CLI commands that answer questions: ask, serve, cache-clear and the golden eval.

Why a separate module: cli.py holds the data commands (ingest, build, index, search, dq,
crosscheck); keeping each file under 300 lines keeps it readable. cli.py registers these.
"""

from pathlib import Path
from typing import Annotated

import typer

from safetylens.answer import golden as golden_eval
from safetylens.answer import golden_report, runtime
from safetylens.config import Settings
from safetylens.ingest.pipeline import DB_NAME
from safetylens.store import db


def ask(question: str) -> None:
    """Answer a question about NHTSA complaints and recalls, with citations (uses the API)."""
    settings = Settings()
    llm = runtime.build_llm(settings, "ask")
    with db.connect(settings.data_dir / DB_NAME, read_only=True) as con:
        engine = runtime.build_engine(settings, con, llm, runtime.build_cache(settings))
        answer = engine.ask(question)
    typer.echo(answer.text)
    typer.echo(
        f"\n[{answer.status}{', cached' if answer.cached else ''}] "
        f"citations: {', '.join(answer.citations) or 'none'} | "
        f"cost ${answer.cost_usd:.4f} | {answer.latency_s:.1f}s"
    )
    if answer.first_draft_errors:
        typer.echo(f"first draft rejected: {'; '.join(answer.first_draft_errors)}")
    typer.echo(
        "Complaints are unverified consumer reports filed with NHTSA. Counts are not defect rates."
    )


def serve(
    port: Annotated[int, typer.Option(help="port to listen on")] = 8000,
    host: Annotated[str, typer.Option(help="0.0.0.0 only inside a container")] = "127.0.0.1",
) -> None:
    """Run the web app (uses the API for answers; record pages are offline)."""
    import uvicorn

    from safetylens.web.app import create_app

    settings = Settings()
    llm = runtime.build_llm(settings, "ask")
    with db.connect(settings.data_dir / DB_NAME, read_only=True) as con:
        # Built once, so the embedder and reranker are loaded before the first question.
        engine = runtime.build_engine(settings, con, llm, runtime.build_cache(settings))
        uvicorn.run(create_app(con, engine), host=host, port=port, log_level="warning")


def cache_clear() -> None:
    """Delete every cached answer (they also stop matching when the data or prompts change)."""
    removed = runtime.build_cache(Settings()).clear()
    typer.echo(f"removed {removed} cached answers")


def eval_answers(
    golden: Annotated[Path, typer.Option(help="golden questions")] = Path("evals/golden.yaml"),
    report_dir: Annotated[Path, typer.Option(help="where the report goes")] = Path("evals/reports"),
    ids: Annotated[str | None, typer.Option(help="comma-separated item ids to run")] = None,
) -> None:
    """Run the golden questions with the real API; exit 1 unless D5/D6/D7/D9 hold."""
    settings = Settings()
    items = golden_eval.load_golden(golden)
    if ids:
        wanted = set(ids.split(","))
        items = [i for i in items if i.id in wanted]
    llm = runtime.build_llm(settings, "eval")
    with db.connect(settings.data_dir / DB_NAME, read_only=True) as con:
        report = golden_eval.run_golden(runtime.build_engine(settings, con, llm), items)
        path = golden_report.write_markdown(report, report_dir)
        # A subset run must not overwrite the full run's review the owner may be spot-checking.
        review_dir = settings.data_dir / "eval" / ("subset" if ids else "")
        review = golden_report.write_judge_review(report, review_dir)
    typer.echo(golden_report.format_summary(report))
    typer.echo(f"report: {path}")
    typer.echo(f"judge verdicts for spot-checking (git-ignored): {review}")
    if not report.passed():
        raise typer.Exit(1)
