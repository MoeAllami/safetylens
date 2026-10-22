-- Row count for a table named by a bound parameter (no table name is spliced into SQL text).
SELECT count(*) FROM query_table(?)
