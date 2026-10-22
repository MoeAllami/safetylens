"""Command-line entry point.

Typer builds the CLI from type hints; later phases add index, search, ask, eval and serve.
"""

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import httpx
import typer

from safetylens import __version__
from safetylens.config import Settings
from safetylens.crosscheck.crosscheck import crosscheck, format_table, load_vehicles
from safetylens.crosscheck.nhtsa_api import NhtsaApi
from safetylens.dq import format_report, run_checks
from safetylens.ingest.pipeline import DB_NAME, KINDS, run_ingest
from safetylens.store import db
from safetylens.store.build import BUILT_TABLES, build

app = typer.Typer(help="SafetyLens: cited answers about NHTSA complaints and recalls.")


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
