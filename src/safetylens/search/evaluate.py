"""Retrieval eval (gate D8): capped recall@10 for BM25, dense and hybrid on judged queries.

Why capped recall: a query can have 30 relevant complaints, but only 10 fit in the top 10, so
plain recall could never reach 1.0. recall@10 = |relevant in top 10| / min(|relevant|, 10).
Labels come from pooled judgments (top 20 of each method, judged by hand); complaints nobody
judged count as not relevant, and how many of those reach a top 10 is reported as a warning.
"""

import datetime as dt
from pathlib import Path
from statistics import mean

import duckdb
import yaml
from pydantic import BaseModel

from safetylens.analytics.templates import VehicleFilter
from safetylens.search.embed import Embedder
from safetylens.search.search import Method, search

METHODS: tuple[Method, ...] = ("bm25", "dense", "hybrid")
K = 10
TARGET = 0.80


class RetrievalQuery(BaseModel):
    id: str
    make: str
    model: str
    year: int
    query: str
    component_system: str | None = None

    def vehicle_filter(self) -> VehicleFilter:
        return VehicleFilter(
            make=self.make,
            model=self.model,
            year_from=self.year,
            year_to=self.year,
            component_system=self.component_system,
        )


class LabeledQuery(RetrievalQuery):
    relevant: list[str]
    not_relevant: list[str] = []


class QueryResult(BaseModel):
    id: str
    recall: dict[str, float]
    unjudged_in_top: dict[str, int]


class RetrievalReport(BaseModel):
    date: dt.date
    queries: list[QueryResult]
    skipped: list[str]  # queries with no relevant complaint (recall undefined)

    def mean_recall(self, method: str) -> float:
        return mean(q.recall[method] for q in self.queries) if self.queries else 0.0

    def passed(self) -> bool:
        hybrid = self.mean_recall("hybrid")
        return (
            hybrid >= TARGET
            and hybrid > self.mean_recall("bm25")
            and hybrid > self.mean_recall("dense")
        )


def recall_at_k(ranked: list[str], relevant: set[str], k: int = K) -> float | None:
    if not relevant:
        return None
    return len(relevant.intersection(ranked[:k])) / min(len(relevant), k)


def load_queries(path: Path) -> list[RetrievalQuery]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [RetrievalQuery.model_validate(q) for q in data["queries"]]


def load_labels(path: Path) -> list[LabeledQuery]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [LabeledQuery.model_validate(q) for q in data["queries"]]


def ranked_ids(
    con: duckdb.DuckDBPyConnection, q: RetrievalQuery, method: Method, k: int, embedder: Embedder
) -> list[str]:
    hits = search(con, q.vehicle_filter(), q.query, method=method, k=k, embedder=embedder)
    return [h.odino for h in hits]


def pool(
    con: duckdb.DuckDBPyConnection, q: RetrievalQuery, embedder: Embedder, depth: int = 20
) -> list[str]:
    """Union of every method's top `depth`: the candidates a person judges for one query."""
    seen: dict[str, None] = {}
    for method in METHODS:
        for odino in ranked_ids(con, q, method, depth, embedder):
            seen.setdefault(odino, None)
    return list(seen)


def evaluate(
    con: duckdb.DuckDBPyConnection,
    labels: list[LabeledQuery],
    embedder: Embedder,
    today: dt.date | None = None,
) -> RetrievalReport:
    results: list[QueryResult] = []
    skipped: list[str] = []
    for q in labels:
        relevant = set(q.relevant)
        if not relevant:
            skipped.append(q.id)
            continue
        judged = relevant | set(q.not_relevant)
        recall: dict[str, float] = {}
        unjudged: dict[str, int] = {}
        for method in METHODS:
            top = ranked_ids(con, q, method, K, embedder)
            value = recall_at_k(top, relevant)
            recall[method] = 0.0 if value is None else value
            unjudged[method] = sum(1 for odino in top if odino not in judged)
        results.append(QueryResult(id=q.id, recall=recall, unjudged_in_top=unjudged))
    return RetrievalReport(date=today or dt.date.today(), queries=results, skipped=skipped)


def format_summary(report: RetrievalReport) -> str:
    lines = [f"{'method':<8} {'recall@10':>9} {'unjudged in top 10':>19}"]
    for method in METHODS:
        unjudged = sum(q.unjudged_in_top[method] for q in report.queries)
        lines.append(f"{method:<8} {report.mean_recall(method):>9.3f} {unjudged:>19}")
    verdict = "PASS" if report.passed() else "FAIL"
    lines.append(
        f"{verdict}: hybrid >= {TARGET:.2f} and beats bm25 and dense "
        f"({len(report.queries)} queries, {len(report.skipped)} skipped)"
    )
    return "\n".join(lines)


def write_markdown(report: RetrievalReport, report_dir: Path) -> Path:
    """Numbers and ODI-free query ids only; never narratives."""
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"retrieval-{report.date.isoformat()}.md"
    rows = [
        f"| {q.id} | " + " | ".join(f"{q.recall[m]:.2f}" for m in METHODS) + " |"
        for q in report.queries
    ]
    body = [
        f"# Retrieval eval {report.date.isoformat()}",
        "",
        "```",
        format_summary(report),
        "```",
        "",
        "| query | bm25 | dense | hybrid |",
        "|---|---|---|---|",
        *rows,
    ]
    if report.skipped:
        body += ["", f"Skipped (no relevant complaint): {', '.join(report.skipped)}"]
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    return path
