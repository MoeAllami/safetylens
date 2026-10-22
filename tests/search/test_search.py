import duckdb
import pytest

from safetylens.analytics.templates import VehicleFilter
from safetylens.search.embed import EMBED_DIM, HashingEmbedder
from safetylens.search.search import rrf, search, snippet

F150 = VehicleFilter(make="FORD", model="F-150", year_from=2022, year_to=2022)
EMB = HashingEmbedder()


def test_rrf_fuses_by_rank_with_hand_computed_order() -> None:
    # a: 1/61 = .01639   b: 1/62 + 1/61 = .03252   c: 1/63 + 1/62 = .03200   d: 1/63 = .01587
    fused = rrf([["a", "b", "c"], ["b", "c", "d"]])
    assert [doc for doc, _ in fused] == ["b", "c", "a", "d"]
    assert fused[0][1] == pytest.approx(1 / 62 + 1 / 61)


def test_rrf_breaks_ties_by_id() -> None:
    assert [doc for doc, _ in rrf([["y"], ["x"]])] == ["x", "y"]


def test_bm25_stems_and_respects_vehicle_filter(search_db: duckdb.DuckDBPyConnection) -> None:
    hits = search(search_db, F150, "braking problem", method="bm25")
    # "braking" and "brakes" share the stem "brake"; the Camry (5) matches words, not vehicle.
    assert {h.odino for h in hits} == {"1", "2"}
    assert [h.rank for h in hits] == [1, 2]


def test_bm25_returns_nothing_without_matching_words(search_db: duckdb.DuckDBPyConnection) -> None:
    assert search(search_db, F150, "sunroof exploded", method="bm25") == []


def test_dense_ranks_by_similarity(search_db: duckdb.DuckDBPyConnection) -> None:
    hits = search(search_db, F150, "transmission slams into gear", method="dense", embedder=EMB)
    assert hits[0].odino == "3"
    assert "5" not in {h.odino for h in hits}


def test_hybrid_fuses_both_lists(search_db: duckdb.DuckDBPyConnection) -> None:
    hits = search(search_db, F150, "brakes failed", method="hybrid", k=2, embedder=EMB)
    assert [h.odino for h in hits][0] == "1"  # top of both lists
    assert all(h.method == "hybrid" for h in hits)
    assert len(hits) == 2


def test_component_filter_applies(search_db: duckdb.DuckDBPyConnection) -> None:
    steering = F150.model_copy(update={"component_system": "STEERING"})
    assert search(search_db, steering, "brakes", method="bm25") == []


def test_dense_and_hybrid_need_an_embedder(search_db: duckdb.DuckDBPyConnection) -> None:
    with pytest.raises(ValueError, match="needs an embedder"):
        search(search_db, F150, "brakes", method="dense")


def test_unknown_method_is_rejected(search_db: duckdb.DuckDBPyConnection) -> None:
    with pytest.raises(ValueError, match="unknown search method"):
        search(search_db, F150, "brakes", method="magic")  # type: ignore[arg-type]


def test_snippet_is_trimmed(search_db: duckdb.DuckDBPyConnection) -> None:
    assert snippet(search_db, "3", chars=12) == "TRANSMISSION"
    assert snippet(search_db, "nope") == ""


def test_hashing_embedder_is_unit_length() -> None:
    vec = EMB.embed_query("brake pedal")
    assert len(vec) == EMBED_DIM
    assert sum(v * v for v in vec) == pytest.approx(1.0)
