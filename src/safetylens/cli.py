"""Command-line entry point.

Typer builds the CLI from type hints; later phases add ingest, search, ask, eval and serve.
"""

import typer

from safetylens import __version__

app = typer.Typer(help="SafetyLens: cited answers about NHTSA complaints and recalls.")


@app.callback()
def main() -> None:
    """Keep Typer in multi-command mode so `version` stays a subcommand."""


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)
