-- rows, distinct complaints (ODINO repeats per component, so never count rows as complaints),
-- and an order-independent checksum used to prove a re-run loads identical data.
SELECT
    count(*) AS row_count,
    count(DISTINCT odino) AS distinct_odino,
    CAST(coalesce(sum(CAST(hash(t) AS HUGEINT)), 0) AS VARCHAR) AS checksum
FROM complaints_raw AS t
