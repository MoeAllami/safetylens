-- A complaint may list several components, but the same (odino, component) pair twice is a duplicate.
SELECT count(*)
FROM (
    SELECT odino, compdesc
    FROM complaints_raw
    GROUP BY odino, compdesc
    HAVING count(*) > 1
)
