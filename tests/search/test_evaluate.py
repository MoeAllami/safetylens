import datetime as dt
from pathlib import Path

import duckdb

from safetylens.search.embed import HashingEmbedder
from safetylens.search.evaluate import (
    LabeledQuery,
    QueryResult,
    RetrievalReport,
    evaluate,
    load_queries,
    pool,
    recall_at_k,
    write_markdown,
)


def _labeled(qid: str, query: str, relevant: list[str], not_relevant: list[str]) -> LabeledQuery:
    return LabeledQuery(
        id=qid,
        make="FORD",
        model="F-150",
        year=2022,
        query=query,
        relevant=relevant,
        not_relevant=not_relevant,
    )


def test_recall_is_capped_at_k() -> None:
    ranked = [str(i) for i in range(20)]
    assert recall_at_k(ranked, {"0", "5", "99"}) == 2 / 3
    assert recall_at_k(ranked, {str(i) for i in range(15)}) == 1.0  # 10 of 15 fit: denominator 10
    assert recall_at_k(ranked, {"10", "11"}) == 0.0  # ranks 11 and 12 are outside the top 10
    assert recall_at_k(ranked, set()) is None


def _report(bm25: float, dense: float, hybrid: float) -> RetrievalReport:
    q = QueryResult(
        id="q",
        recall={"bm25": bm25, "dense": dense, "hybrid": hybrid},
        unjudged_in_top={"bm25": 0, "dense": 0, "hybrid": 0},
    )
    return RetrievalReport(date=dt.date(2026, 1, 1), queries=[q], skipped=[])


def test_gate_requires_target_and_beating_both() -> None:
    assert _report(0.70, 0.80, 0.85).passed()
    assert not _report(0.70, 0.75, 0.79).passed()  # below 0.80
    assert not _report(0.85, 0.70, 0.85).passed()  # ties BM25 instead of beating it
    assert not _report(0.70, 0.90, 0.85).passed()  # dense alone is better


def test_evaluate_counts_unjudged_and_skips_empty(search_db: duckdb.DuckDBPyConnection) -> None:
    labels = [
        _labeled("q1", "transmission slams into gear", ["3"], ["4"]),
        _labeled("q2", "anything", [], []),
    ]
    report = evaluate(search_db, labels, HashingEmbedder(), today=dt.date(2026, 1, 2))
    assert report.skipped == ["q2"]
    (q1,) = report.queries
    assert q1.recall == {"bm25": 1.0, "dense": 1.0, "hybrid": 1.0}
    assert q1.unjudged_in_top["bm25"] == 0  # BM25 only returns the one matching complaint
    assert q1.unjudged_in_top["dense"] == 2  # 1 and 2 were never judged for q1
    assert not report.passed()  # perfect but tied: hybrid does not beat the others


def test_pool_is_union_of_methods(search_db: duckdb.DuckDBPyConnection) -> None:
    q = _labeled("q", "brakes failed", [], [])
    candidates = pool(search_db, q, HashingEmbedder(), depth=2)
    assert len(candidates) == len(set(candidates))
    assert "1" in candidates
    assert "5" not in candidates  # other vehicle


def test_markdown_report_has_no_narratives(
    search_db: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    labels = [_labeled("q1", "transmission slams into gear", ["3"], [])]
    report = evaluate(search_db, labels, HashingEmbedder(), today=dt.date(2026, 1, 2))
    path = write_markdown(report, tmp_path / "reports")
    text = path.read_text(encoding="utf-8")
    assert path.name == "retrieval-2026-01-02.md"
    assert "| q1 | 1.00 | 1.00 | 1.00 |" in text
    assert "TRANSMISSION" not in text


def test_committed_queries_file_parses() -> None:
    queries = load_queries(Path(__file__).parents[2] / "evals" / "retrieval_queries.yaml")
    assert len(queries) == 60
    assert len({q.id for q in queries}) == 60
