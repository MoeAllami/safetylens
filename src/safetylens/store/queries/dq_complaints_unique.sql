-- complaints grain: exactly one row per (odino, component).
SELECT count(*)
FROM (
    SELECT odino, component
    FROM complaints
    GROUP BY odino, component
    HAVING count(*) > 1
)
