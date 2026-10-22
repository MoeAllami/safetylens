"""Command-line entry point.

Typer builds the CLI from type hints; later phases add index, search, ask, eval and serve.
"""

from enum import StrEnum
from typing import Annotated

import httpx
import typer

from safetylens import __version__
from safetylens.config import Settings
from safetylens.dq import format_report, run_checks
from safetylens.ingest.pipeline import DB_NAME, KINDS, run_ingest
from safetylens.store import db

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
            f"rejected {st.rows_rejected}, undecodable-byte rows {st.rows_replaced}, "
            f"bad values {st.bad_values}"
        )


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
