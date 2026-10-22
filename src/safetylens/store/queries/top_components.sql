-- Components ranked by distinct complaints. A complaint listing two components counts once in each.
SELECT
    component_system,
    component,
    count(DISTINCT odino) AS complaints,
    count(DISTINCT odino) FILTER (WHERE crash) AS crashes,
    count(DISTINCT odino) FILTER (WHERE fire) AS fires
FROM complaints
WHERE make = $make
    AND model_key = $model_key
    AND ($year_from IS NULL OR model_year >= $year_from)
    AND ($year_to IS NULL OR model_year <= $year_to)
    AND ($received_from IS NULL OR received_date >= $received_from)
    AND ($received_to IS NULL OR received_date <= $received_to)
    AND ($component_system IS NULL OR component_system = $component_system)
GROUP BY component_system, component
ORDER BY complaints DESC, component
LIMIT $limit
