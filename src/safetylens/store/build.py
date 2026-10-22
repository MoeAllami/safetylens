"""Build the normalized tables from the raw layer.

Why one transaction: the tables depend on each other (docs come from complaints, aliases from
models), so either the whole set is rebuilt or none of it is; a failed build never leaves a mix.
"""

from importlib.resources import as_file, files

import duckdb

from safetylens.store.sql import load_sql

BUILD_STEPS = (
    "build_complaints",
    "build_recalls",
    "build_component_systems",
    "build_complaint_docs",
    "build_vehicle_models",
)
BUILT_TABLES = (
    "complaints",
    "recalls",
    "component_systems",
    "complaint_docs",
    "vehicle_models",
    "model_aliases",
)


def build(con: duckdb.DuckDBPyConnection) -> None:
    con.begin()
    try:
        for step in BUILD_STEPS:
            con.execute(load_sql(step))
        with as_file(files("safetylens.store").joinpath("model_aliases.csv")) as csv_path:
            con.execute(load_sql("build_model_aliases"), [csv_path.as_posix()])
    except BaseException:
        con.rollback()
        raise
    con.commit()
