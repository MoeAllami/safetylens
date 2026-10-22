-- recalls grain: one row per (campaign, vehicle, component).
SELECT count(*)
FROM (
    SELECT campno, make, model, model_year, component
    FROM recalls
    GROUP BY ALL
    HAVING count(*) > 1
)
