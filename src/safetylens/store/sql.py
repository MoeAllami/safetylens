"""Load SQL templates by name so queries live in .sql files, never in f-strings."""

from importlib.resources import files


def load_sql(name: str) -> str:
    return files("safetylens.store.queries").joinpath(f"{name}.sql").read_text(encoding="utf-8")
