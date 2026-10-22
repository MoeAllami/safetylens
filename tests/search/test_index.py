from pathlib import Path

import duckdb
import pytest
from builders import make_search_db

from safetylens.search.embed import HashingEmbedder
from safetylens.search.index import embed_docs, load_fts


class RenamedEmbedder(HashingEmbedder):
    name = "another-model"


def test_second_run_embeds_nothing(search_db: duckdb.DuckDBPyConnection) -> None:
    stats = embed_docs(search_db, HashingEmbedder())
    assert (stats.embedded, stats.already_current) == (0, 5)


def test_changed_narrative_is_re_embedded_alone(search_db: duckdb.DuckDBPyConnection) -> None:
    search_db.execute("UPDATE complaint_docs SET narrative = 'NEW TEXT' WHERE odino = '4'")
    stats = embed_docs(search_db, HashingEmbedder())
    assert stats.embedded == 1
    row = search_db.execute("SELECT count(*) FROM doc_embeddings WHERE odino = '4'").fetchone()
    assert row == (1,)  # replaced, not duplicated


def test_new_model_re_embeds_everything(search_db: duckdb.DuckDBPyConnection) -> None:
    assert embed_docs(search_db, RenamedEmbedder()).embedded == 5


def test_resumes_in_chunks_with_progress(tmp_path: Path) -> None:

    con = make_search_db(tmp_path)
    con.execute("DELETE FROM doc_embeddings WHERE odino IN ('2', '3', '4')")
    seen: list[tuple[int, int]] = []
    stats = embed_docs(
        con, HashingEmbedder(), chunk=2, on_progress=lambda d, t: seen.append((d, t))
    )
    assert stats.embedded == 3
    assert seen == [(2, 3), (3, 3)]
    assert stats.docs_per_second > 0


def test_missing_fts_extension_has_clear_error() -> None:
    class NoExtensions:
        def load_extension(self, _name: str) -> None:
            raise duckdb.IOException("extension not found")

    with pytest.raises(RuntimeError, match="make install"):
        load_fts(NoExtensions())  # type: ignore[arg-type]
