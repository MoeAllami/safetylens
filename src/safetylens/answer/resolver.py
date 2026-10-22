"""Map how a person names a vehicle ("Chevy Silverado", "F150 pickup") to our make and model_key.

Why ask instead of guess: answering about the wrong vehicle is worse than asking. An exact alias
wins; otherwise fuzzy matching must find one clear winner, or the user gets a short list.
"""

import csv
from importlib.resources import files
from typing import Literal

import duckdb
from pydantic import BaseModel
from rapidfuzz import fuzz, process

from safetylens.analytics.templates import model_key
from safetylens.answer.models import ResolvedVehicle, VehicleRef
from safetylens.store.sql import load_sql

SURE = 90.0  # fuzzy score needed to accept a match without asking
MARGIN = 5.0  # ...and how far ahead of the runner-up it must be
CONSIDER = 70.0  # below this a candidate is not even offered
MAKE_SURE = 85.0  # make typos ("TOYTOA") are fixed; unrelated names are not


class Resolution(BaseModel):
    status: Literal["ok", "clarify"]
    vehicle: ResolvedVehicle | None = None
    options: list[str] = []


def _make_aliases() -> dict[str, str]:
    text = files("safetylens.store").joinpath("make_aliases.csv").read_text(encoding="utf-8")
    return {row["alias"].upper(): row["make"].upper() for row in csv.DictReader(text.splitlines())}


def resolve_make(con: duckdb.DuckDBPyConnection, make: str) -> str | None:
    wanted = _make_aliases().get(make.strip().upper(), make.strip().upper())
    makes = [str(r[0]) for r in con.execute(load_sql("resolver_makes")).fetchall()]
    if wanted in makes:
        return wanted
    # Plain ratio, not WRatio: partial matching would turn "FOO" into "BIGFOOT".
    best = process.extractOne(wanted, makes, scorer=fuzz.ratio)
    return str(best[0]) if best and best[1] >= MAKE_SURE else None


def resolve(con: duckdb.DuckDBPyConnection, ref: VehicleRef) -> Resolution:
    year_from = ref.year_from or ref.year_to
    year_to = ref.year_to or ref.year_from
    make = resolve_make(con, ref.make)
    if make is None:
        return Resolution(status="clarify", options=[f"No manufacturer matches '{ref.make}'."])

    def done(key: str, display: str) -> Resolution:
        vehicle = ResolvedVehicle(
            make=make, model=display, model_key=key, year_from=year_from, year_to=year_to
        )
        return Resolution(status="ok", vehicle=vehicle)

    wanted = model_key(ref.model)
    models = con.execute(load_sql("resolver_models"), {"make": make}).fetchall()
    display = {str(r[0]): str(r[1]) for r in models}
    alias = con.execute(load_sql("resolver_alias"), {"make": make, "alias_key": wanted}).fetchall()
    if len(alias) == 1:
        key = str(alias[0][0])
        return done(key, display.get(key, ref.model.upper()))

    scored = process.extract(wanted, list(display), scorer=fuzz.WRatio, limit=5)
    good = [(str(key), float(score)) for key, score, _ in scored if score >= CONSIDER]
    if good and good[0][1] >= SURE and (len(good) == 1 or good[0][1] - good[1][1] >= MARGIN):
        return done(good[0][0], display[good[0][0]])
    options = [f"{make} {display[key]}" for key, _ in good[:3]]
    if not options:
        options = [f"No {make} model matches '{ref.model}'."]
    return Resolution(status="clarify", options=options)
