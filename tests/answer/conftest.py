import datetime as dt
from pathlib import Path

import duckdb
import pytest
from builders import complaint_line, make_db, recall_line

from safetylens.answer.llm import FakeLLM
from safetylens.answer.models import QueryPlan, VehicleRef
from safetylens.answer.pipeline import Engine
from safetylens.search.embed import HashingEmbedder
from safetylens.search.index import build_fts, embed_docs
from safetylens.search.rerank import OverlapReranker

# Realistic 8-digit ODI numbers so bracket citations look like the real thing.
F150 = {
    "11000001": ("THE BRAKES FAILED AND THE PEDAL WENT TO THE FLOOR", "SERVICE BRAKES, HYDRAULIC"),
    "11000002": ("BRAKING DISTANCE INCREASED, BRAKE PEDAL FEELS SOFT", "SERVICE BRAKES, HYDRAULIC"),
    "11000003": ("TRANSMISSION SLAMS INTO GEAR WHEN SHIFTING", "POWER TRAIN"),
    "11000004": ("THE RADIO SCREEN WENT BLACK WHILE DRIVING", "ELECTRICAL SYSTEM"),
}


def answer_lines() -> list[str]:
    lines = [
        complaint_line(odino, compdesc=comp, narrative=text, p17="20240115")
        for odino, (text, comp) in F150.items()
    ]
    lines.append(
        complaint_line(
            "11000009", narrative="BRAKES FAILED", p4="TOYOTA", p5="CAMRY", p17="20240301"
        )
    )
    return lines


@pytest.fixture
def answer_db(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    con = make_db(tmp_path, answer_lines(), [recall_line("22V123000")])
    build_fts(con)
    embed_docs(con, HashingEmbedder())
    return con


def plan(intent: str = "top_components", model: str = "F-150", **extra: object) -> QueryPlan:
    return QueryPlan.model_validate(
        {
            "intent": intent,
            "vehicle": VehicleRef(make="Ford", model=model, year_from=2022, year_to=2022),
            "search_text": "brakes failed",
            **extra,
        }
    )


def engine(con: duckdb.DuckDBPyConnection, llm: FakeLLM) -> Engine:
    return Engine(
        con=con,
        llm=llm,
        embedder=HashingEmbedder(),
        reranker=OverlapReranker(),
        rerank_depth=4,
        today=dt.date(2026, 1, 1),
    )
