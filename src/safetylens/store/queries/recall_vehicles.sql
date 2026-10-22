-- The vehicles and components a recall campaign covers, one row per make/model/year.
SELECT
    make,
    model,
    model_year,
    list(DISTINCT component ORDER BY component) AS components
FROM recalls
WHERE campno = $campno
GROUP BY make, model, model_year
ORDER BY make, model, model_year NULLS LAST
