"""A small indexed database and a web app wired to a scripted FakeLLM (no network, no API)."""

import datetime as dt
from pathlib import Path

import duckdb
from builders import complaint_line, make_db, recall_line

from safetylens.answer.llm import FakeLLM
from safetylens.answer.models import QueryPlan, VehicleRef, WriterOutput
from safetylens.answer.pipeline import Engine
from safetylens.search.embed import HashingEmbedder
from safetylens.search.index import build_fts, embed_docs
from safetylens.search.rerank import OverlapReranker

COMPLAINTS = {
    "11000001": ("THE BRAKES FAILED AND THE PEDAL WENT TO THE FLOOR", "SERVICE BRAKES, HYDRAULIC"),
    "11000002": ("BRAKING DISTANCE INCREASED, BRAKE PEDAL FEELS SOFT", "SERVICE BRAKES, HYDRAULIC"),
    "11000003": ("TRANSMISSION SLAMS INTO GEAR WHEN SHIFTING", "POWER TRAIN"),
}
PLAN = QueryPlan(
    intent="top_components",
    vehicle=VehicleRef(make="Ford", model="F-150", year_from=2022, year_to=2022),
    search_text="brakes failed",
)
GOOD = WriterOutput(
    answer_markdown="The 2022 F-150 has 3 complaints; owners report brake failure [11000001].",
    citations=["11000001"],
)


def web_db(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    lines = [
        complaint_line(odino, compdesc=comp, narrative=text, p17="20240115")
        for odino, (text, comp) in COMPLAINTS.items()
    ]
    con = make_db(tmp_path, lines, [recall_line("22V123000")])
    build_fts(con)
    embed_docs(con, HashingEmbedder())
    return con


def web_engine(con: duckdb.DuckDBPyConnection, llm: FakeLLM) -> Engine:
    return Engine(
        con=con,
        llm=llm,
        embedder=HashingEmbedder(),
        reranker=OverlapReranker(),
        rerank_depth=4,
        today=dt.date(2026, 1, 1),
    )
