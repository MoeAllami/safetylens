CREATE OR REPLACE TABLE complaints_raw AS
SELECT * FROM read_parquet(?)
