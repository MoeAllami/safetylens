CREATE OR REPLACE TABLE recalls_raw AS
SELECT * FROM read_parquet(?)
