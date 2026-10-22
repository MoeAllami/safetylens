"""Retrieval eval (gate D8): capped recall@10 for BM25, dense, hybrid and reranked hybrid.

Why capped recall: a query can have 30 relevant complaints, but only 10 fit in the top 10, so
plain recall could never reach 1.0. recall@10 = |relevant in top 10| / min(|relevant|, 10).
Labels come from pooled judgments (top 20 of BM25, dense and hybrid, judged by hand); complaints
nobody judged count as not relevant, and how many of those reach a top 10 is reported.

Why a dev/test split: settings (like rerank depth) are chosen by looking at dev queries (odd ids)
only; the gate is measured on test queries (even ids), so tuning cannot inflate the number.
"""

import datetime as dt
from pathlib import Path
from statistics import mean
from typing import Literal

import duckdb
import yaml
from pydantic import BaseModel

from safetylens.analytics.templates import VehicleFilter
from safetylens.search.embed import Embedder
from safetylens.search.rerank import Reranker
from safetylens.search.search import METHOD_NAMES, RERANK_DEPTH, Method, search

POOL_METHODS: tuple[Method, ...] = ("bm25", "dense", "hybrid")  # what the labels were pooled from
GATE_METHOD: Method = "rerank"
K = 10
TARGET = 0.80
Split = Literal["dev", "test"]


class RetrievalQuery(BaseModel):
    id: str
    make: str
    model: str
    year: int
    query: str
    component_system: str | None = None

    @property
    def split(self) -> Split:
        return "dev" if int(self.id.lstrip("q")) % 2 else "test"

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
    split: Split
    recall: dict[str, float]
    unjudged_in_top: dict[str, int]


class RetrievalReport(BaseModel):
    date: dt.date
    methods: list[Method]
    queries: list[QueryResult]
    skipped: list[str]  # queries with no relevant complaint (recall undefined)

    def mean_recall(self, method: str, split: Split | None = None) -> float:
        values = [q.recall[method] for q in self.queries if split is None or q.split == split]
        return mean(values) if values else 0.0

    def gate_method(self) -> Method:
        return GATE_METHOD if GATE_METHOD in self.methods else "hybrid"

    def passed(self) -> bool:
        """Gate on test queries only: the production method reaches TARGET and beats both bases."""
        best = self.mean_recall(self.gate_method(), "test")
        return (
            best >= TARGET
            and best > self.mean_recall("bm25", "test")
            and best > self.mean_recall("dense", "test")
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
    con: duckdb.DuckDBPyConnection,
    q: RetrievalQuery,
    method: Method,
    k: int,
    embedder: Embedder,
    reranker: Reranker | None = None,
    rerank_depth: int = RERANK_DEPTH,
) -> list[str]:
    hits = search(
        con,
        q.vehicle_filter(),
        q.query,
        method=method,
        k=k,
        embedder=embedder,
        reranker=reranker,
        rerank_depth=rerank_depth,
    )
    return [h.odino for h in hits]


def pool(
    con: duckdb.DuckDBPyConnection, q: RetrievalQuery, embedder: Embedder, depth: int = 20
) -> list[str]:
    """Union of every pooling method's top `depth`: the candidates a person judges for one query."""
    seen: dict[str, None] = {}
    for method in POOL_METHODS:
        for odino in ranked_ids(con, q, method, depth, embedder):
            seen.setdefault(odino, None)
    return list(seen)


def evaluate(
    con: duckdb.DuckDBPyConnection,
    labels: list[LabeledQuery],
    embedder: Embedder,
    reranker: Reranker | None = None,
    *,
    rerank_depth: int = RERANK_DEPTH,
    today: dt.date | None = None,
) -> RetrievalReport:
    methods = [m for m in METHOD_NAMES if m != "rerank" or reranker is not None]
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
        for method in methods:
            top = ranked_ids(con, q, method, K, embedder, reranker, rerank_depth)
            value = recall_at_k(top, relevant)
            recall[method] = 0.0 if value is None else value
            unjudged[method] = sum(1 for odino in top if odino not in judged)
        results.append(QueryResult(id=q.id, split=q.split, recall=recall, unjudged_in_top=unjudged))
    return RetrievalReport(
        date=today or dt.date.today(), methods=methods, queries=results, skipped=skipped
    )


def format_summary(report: RetrievalReport) -> str:
    n_dev = sum(1 for q in report.queries if q.split == "dev")
    n_test = len(report.queries) - n_dev
    lines = [
        f"{'method':<8} {'all':>6} {'dev':>6} {'test':>6} {'unjudged in top 10':>19}",
    ]
    for method in report.methods:
        unjudged = sum(q.unjudged_in_top[method] for q in report.queries)
        lines.append(
            f"{method:<8} {report.mean_recall(method):>6.3f} "
            f"{report.mean_recall(method, 'dev'):>6.3f} {report.mean_recall(method, 'test'):>6.3f} "
            f"{unjudged:>19}"
        )
    verdict = "PASS" if report.passed() else "FAIL"
    lines.append(
        f"{verdict}: {report.gate_method()} recall@10 on test >= {TARGET:.2f} and beats bm25 and "
        f"dense (dev {n_dev}, test {n_test}, skipped {len(report.skipped)})"
    )
    return "\n".join(lines)


def write_markdown(report: RetrievalReport, report_dir: Path) -> Path:
    """Numbers and query ids only; never narratives."""
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"retrieval-{report.date.isoformat()}.md"
    header = "| query | split | " + " | ".join(report.methods) + " |"
    rows = [
        f"| {q.id} | {q.split} | " + " | ".join(f"{q.recall[m]:.2f}" for m in report.methods) + " |"
        for q in report.queries
    ]
    body = [
        f"# Retrieval eval {report.date.isoformat()}",
        "",
        "```",
        format_summary(report),
        "```",
        "",
        header,
        "|" + "---|" * (len(report.methods) + 2),
        *rows,
    ]
    if report.skipped:
        body += ["", f"Skipped (no relevant complaint): {', '.join(report.skipped)}"]
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    return path
