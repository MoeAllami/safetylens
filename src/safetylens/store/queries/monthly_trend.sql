-- Distinct complaints per month received. Months with no complaints are filled with 0 here in SQL,
-- so every number shown in a chart comes from this query. With a received range the series spans
-- the whole range; without one it spans the first to the last month that has complaints.
WITH counts AS (
    SELECT
        CAST(date_trunc('month', received_date) AS DATE) AS month,
        count(DISTINCT odino) AS complaints
    FROM complaints
    WHERE make = $make
        AND model_key = $model_key
        AND ($year_from IS NULL OR model_year >= $year_from)
        AND ($year_to IS NULL OR model_year <= $year_to)
        AND ($received_from IS NULL OR received_date >= $received_from)
        AND ($received_to IS NULL OR received_date <= $received_to)
        AND ($component_system IS NULL OR component_system = $component_system)
    GROUP BY 1
),
months AS (
    SELECT CAST(unnest(generate_series(
        coalesce(CAST(date_trunc('month', CAST($received_from AS DATE)) AS DATE), min(month)),
        coalesce(CAST(date_trunc('month', CAST($received_to AS DATE)) AS DATE), max(month)),
        INTERVAL 1 MONTH
    )) AS DATE) AS month
    FROM counts
)
SELECT m.month, coalesce(c.complaints, 0) AS complaints
FROM months AS m
LEFT JOIN counts AS c USING (month)
ORDER BY m.month
