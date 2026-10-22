"""Check a written answer before anyone sees it (gates D5 and D6).

Two rules, enforced in code rather than trusted to the prompt:
- every number in the prose must appear in the SQL results (or the vehicle / date filters);
- every citation must be in the evidence the writer was given and must exist in the database.
"""

import duckdb

from safetylens.answer.numbers import citations_in, numbers_in
from safetylens.store.sql import load_sql


def existing_ids(con: duckdb.DuckDBPyConnection, ids: list[str]) -> set[str]:
    if not ids:
        return set()
    return {str(r[0]) for r in con.execute(load_sql("citation_exists"), {"ids": ids}).fetchall()}


def validate(
    con: duckdb.DuckDBPyConnection,
    text: str,
    declared_citations: list[str],
    allowed_numbers: set[str],
    allowed_citations: set[str],
) -> list[str]:
    errors: list[str] = []
    stray = sorted(numbers_in(text) - allowed_numbers, key=lambda n: (len(n), n))
    if stray:
        errors.append(
            "numbers not in the SQL results: "
            + ", ".join(stray)
            + " (use only numbers from the provided rows; do not compute or quote other numbers)"
        )
    cited = list(dict.fromkeys(citations_in(text) + declared_citations))
    outside = [c for c in cited if c not in allowed_citations]
    if outside:
        errors.append("citations not in the provided evidence: " + ", ".join(outside))
    missing = [c for c in cited if c not in existing_ids(con, cited)]
    if missing:
        errors.append("citations that do not exist in the database: " + ", ".join(missing))
    undeclared = [c for c in citations_in(text) if c not in declared_citations]
    if undeclared:
        errors.append(
            "cited in the text but missing from the citations list: " + ", ".join(undeclared)
        )
    return errors
