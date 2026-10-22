SELECT table_name
FROM information_schema.tables
WHERE table_name IN ('complaints_raw', 'recalls_raw', 'ingest_runs')
