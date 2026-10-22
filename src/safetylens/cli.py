"""Command-line entry point.

Typer builds the CLI from type hints; later phases add index, search, ask, eval and serve.
"""

import time
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import httpx
import typer

from safetylens import __version__
from safetylens.analytics.templates import VehicleFilter
from safetylens.answer import golden as golden_eval
from safetylens.answer import golden_report, runtime
from safetylens.config import Settings
from safetylens.crosscheck.crosscheck import crosscheck, format_table, load_vehicles
from safetylens.crosscheck.nhtsa_api import NhtsaApi
from safetylens.dq import format_report, run_checks
from safetylens.ingest.pipeline import DB_NAME, KINDS, run_ingest
from safetylens.search import embed, rerank
from safetylens.search.embed import Embedder
from safetylens.search.evaluate import evaluate, format_summary, load_labels, write_markdown
from safetylens.search.index import build_fts, embed_docs
from safetylens.search.rerank import Reranker
from safetylens.search.search import search, snippet
from safetylens.store import db
from safetylens.store.build import BUILT_TABLES, build

app = typer.Typer(help="SafetyLens: cited answers about NHTSA complaints and recalls.")


class SearchMethod(StrEnum):
    bm25 = "bm25"
    dense = "dense"
    hybrid = "hybrid"
    rerank = "rerank"


class SliceName(StrEnum):
    dev = "dev"
    full = "full"


@app.callback()
def main() -> None:
    """Keep Typer in multi-command mode so subcommands stay subcommands."""


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


@app.command()
def ingest(
    slice_name: Annotated[
        SliceName, typer.Option("--slice", help="dev = 2020+, full = everything")
    ] = SliceName.dev,
) -> None:
    """Download NHTSA files, drop personal data, and load them into DuckDB."""
    settings = Settings()
    timeout = httpx.Timeout(30.0, read=120.0)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        reports, con = run_ingest(settings, slice_name.value, client)
    with con:
        for kind in KINDS:
            if any(r.source.kind == kind for r in reports):
                s = db.summarize(con, kind)
                typer.echo(f"{kind}_raw: {s.row_count} rows, {s.distinct_keys} distinct keys")
    for r in reports:
        st = r.stats
        typer.echo(
            f"{r.source.name}: {r.download_status}, read {st.rows_read}, loaded {st.rows_loaded}, "
            f"rejected {st.rows_rejected}, cp1252-fallback rows {st.rows_cp1252}, "
            f"undecodable-byte rows {st.rows_replaced}, bad values {st.bad_values}"
        )


@app.command("build")
def build_tables() -> None:
    """Rebuild the normalized tables (complaints, complaint_docs, recalls...) from raw."""
    path = Settings().data_dir / DB_NAME
    if not path.exists():
        typer.echo(f"no database at {path}; run `uv run safetylens ingest` first")
        raise typer.Exit(1)
    with db.connect(path) as con:
        build(con)
        for table in BUILT_TABLES:
            typer.echo(f"{table}: {db.count_rows(con, table)} rows")


def _embedder(settings: Settings) -> Embedder:
    return embed.default_embedder(
        settings.embed_model, settings.embed_device, settings.embed_batch_size
    )


def _reranker(settings: Settings) -> Reranker:
    return rerank.default_reranker(settings.rerank_model, settings.embed_device)


@app.command()
def index() -> None:
    """Build the BM25 index and embed any complaints without a current vector (resumable)."""
    settings = Settings()
    path = settings.data_dir / DB_NAME
    if not path.exists():
        typer.echo(f"no database at {path}; run `make data-dev` first")
        raise typer.Exit(1)
    embedder = _embedder(settings)
    with db.connect(path) as con:
        started = time.perf_counter()
        build_fts(con)
        typer.echo(f"bm25 index: built in {time.perf_counter() - started:.1f}s")

        def progress(done: int, total: int) -> None:
            typer.echo(f"embedded {done}/{total}")

        stats = embed_docs(con, embedder, on_progress=progress)
    typer.echo(
        f"embeddings: {stats.embedded} new, {stats.already_current} already current, "
        f"{stats.seconds:.0f}s, {stats.docs_per_second:.0f} docs/s"
    )


@app.command("search")
def search_cmd(
    query: str,
    make: Annotated[str, typer.Option(help="e.g. FORD")],
    model: Annotated[str, typer.Option(help="e.g. F-150")],
    year: Annotated[int | None, typer.Option(help="model year")] = None,
    component_system: Annotated[str | None, typer.Option(help="e.g. 'SERVICE BRAKES'")] = None,
    method: Annotated[
        SearchMethod, typer.Option(help="bm25, dense, hybrid or rerank")
    ] = SearchMethod.rerank,
    k: Annotated[int, typer.Option(help="results to return")] = 8,
) -> None:
    """Show the complaints that best match a problem description for one vehicle."""
    settings = Settings()
    f = VehicleFilter(
        make=make, model=model, year_from=year, year_to=year, component_system=component_system
    )
    embedder = None if method is SearchMethod.bm25 else _embedder(settings)
    reranker = _reranker(settings) if method is SearchMethod.rerank else None
    with db.connect(settings.data_dir / DB_NAME, read_only=True) as con:
        hits = search(
            con,
            f,
            query,
            method=method.value,
            k=k,
            embedder=embedder,
            reranker=reranker,
            rerank_depth=settings.rerank_depth,
        )
        for hit in hits:
            typer.echo(
                f"{hit.rank:>2}. [{hit.odino}] score {hit.score:.4f}  {snippet(con, hit.odino)}"
            )
    if not hits:
        typer.echo("no matching complaints")


@app.command()
def ask(question: str) -> None:
    """Answer a question about NHTSA complaints and recalls, with citations (uses the API)."""
    settings = Settings()
    llm = runtime.build_llm(settings, "ask")
    with db.connect(settings.data_dir / DB_NAME, read_only=True) as con:
        answer = runtime.build_engine(settings, con, llm).ask(question)
    typer.echo(answer.text)
    typer.echo(
        f"\n[{answer.status}] citations: {', '.join(answer.citations) or 'none'} | "
        f"cost ${answer.cost_usd:.4f} | {answer.latency_s:.1f}s"
    )
    if answer.first_draft_errors:
        typer.echo(f"first draft rejected: {'; '.join(answer.first_draft_errors)}")
    typer.echo(
        "Complaints are unverified consumer reports filed with NHTSA. Counts are not defect rates."
    )


@app.command("eval")
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
        review = golden_report.write_judge_review(report, settings.data_dir / "eval")
    typer.echo(golden_report.format_summary(report))
    typer.echo(f"report: {path}")
    typer.echo(f"judge verdicts for spot-checking (git-ignored): {review}")
    if not report.passed():
        raise typer.Exit(1)


@app.command("eval-retrieval")
def eval_retrieval(
    labels: Annotated[Path, typer.Option(help="judged queries")] = Path(
        "evals/retrieval_labels.yaml"
    ),
    report_dir: Annotated[Path, typer.Option(help="where the report goes")] = Path("evals/reports"),
    rerank_depth: Annotated[
        int | None, typer.Option(help="override settings.rerank_depth (choose on dev only)")
    ] = None,
) -> None:
    """Score bm25, dense, hybrid and rerank on judged queries; exit 1 unless the D8 gate holds."""
    settings = Settings()
    embedder = _embedder(settings)
    reranker = _reranker(settings)
    depth = rerank_depth or settings.rerank_depth
    with db.connect(settings.data_dir / DB_NAME, read_only=True) as con:
        report = evaluate(con, load_labels(labels), embedder, reranker, rerank_depth=depth)
    path = write_markdown(report, report_dir)
    typer.echo(format_summary(report))
    typer.echo(f"report: {path}")
    if not report.passed():
        raise typer.Exit(1)


@app.command("crosscheck")
def crosscheck_cmd(
    vehicles: Annotated[Path, typer.Option(help="YAML list of vehicles")] = Path(
        "evals/crosscheck_vehicles.yaml"
    ),
) -> None:
    """Compare our complaint counts with the live NHTSA API; exit 1 if any differ by > 2%."""
    settings = Settings()
    path = settings.data_dir / DB_NAME
    if not path.exists():
        typer.echo(f"no database at {path}; run `make data-dev` first")
        raise typer.Exit(1)
    timeout = httpx.Timeout(30.0, read=120.0)
    with (
        db.connect(path, read_only=True) as con,
        httpx.Client(timeout=timeout, follow_redirects=True) as client,
    ):
        api = NhtsaApi(client, settings.data_dir / "api_cache")
        results = crosscheck(con, api, load_vehicles(vehicles))
    typer.echo(format_table(results))
    if not all(r.passed for r in results):
        raise typer.Exit(1)


@app.command()
def dq() -> None:
    """Run data-quality checks; exit 1 if any fail."""
    path = Settings().data_dir / DB_NAME
    if not path.exists():
        typer.echo(f"[FAIL] no database at {path}; run `make data-dev` first")
        raise typer.Exit(1)
    with db.connect(path, read_only=True) as con:
        results = run_checks(con)
    typer.echo(format_report(results))
    if not all(r.passed for r in results):
        raise typer.Exit(1)
