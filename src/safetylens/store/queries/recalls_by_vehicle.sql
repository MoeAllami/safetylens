-- Recall campaigns covering a vehicle, newest first, one row per campaign.
-- campaigns_total repeats the distinct campaign count on every row so the count comes from SQL.
WITH matched AS (
    SELECT *
    FROM recalls
    WHERE make = $make
        AND model_key = $model_key
        AND ($year_from IS NULL OR model_year >= $year_from)
        AND ($year_to IS NULL OR model_year <= $year_to)
        AND ($component_system IS NULL OR component_system = $component_system)
)
SELECT
    campno,
    min(report_date) AS report_date,
    list(DISTINCT component ORDER BY component) AS components,
    any_value(manufacturer) AS manufacturer,
    max(potentially_affected) AS potentially_affected,
    any_value(consequence) AS consequence,
    any_value(remedy) AS remedy,
    bool_or(do_not_drive) AS do_not_drive,
    bool_or(park_outside) AS park_outside,
    (SELECT count(DISTINCT campno) FROM matched) AS campaigns_total
FROM matched
GROUP BY campno
ORDER BY report_date DESC, campno
