INSERT INTO ingest_runs (
    run_id, started_at, source_name, kind, download_status, sha256,
    rows_read, rows_loaded, rows_rejected, rows_replaced, bad_values, rows_cp1252
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
