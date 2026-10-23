-- Answer cache (SQLite, not DuckDB): one verified answer per normalized-plan key.
CREATE TABLE IF NOT EXISTS answers (key TEXT PRIMARY KEY, answer TEXT NOT NULL)
