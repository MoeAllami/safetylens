CREATE TABLE IF NOT EXISTS ingest_runs (
    run_id VARCHAR NOT NULL,
    started_at TIMESTAMP NOT NULL,
    source_name VARCHAR NOT NULL,
    kind VARCHAR NOT NULL,
    download_status VARCHAR NOT NULL,
    sha256 VARCHAR NOT NULL,
    rows_read BIGINT NOT NULL,
    rows_loaded BIGINT NOT NULL,
    rows_rejected BIGINT NOT NULL,
    rows_replaced BIGINT NOT NULL,
    bad_values BIGINT NOT NULL
)
