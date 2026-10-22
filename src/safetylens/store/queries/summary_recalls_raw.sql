SELECT
    count(*) AS row_count,
    count(DISTINCT campno) AS distinct_campno,
    CAST(coalesce(sum(CAST(hash(t) AS HUGEINT)), 0) AS VARCHAR) AS checksum
FROM recalls_raw AS t
