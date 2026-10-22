from pathlib import Path

import duckdb
import pytest
from builders import make_search_db


@pytest.fixture
def search_db(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    return make_search_db(tmp_path)
