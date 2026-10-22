-- Severity from complaint_docs (one row per complaint), so injuries and deaths are summed once per
-- complaint, not once per component row.
SELECT
    count(DISTINCT odino) AS complaints,
    count(DISTINCT odino) FILTER (WHERE crash) AS with_crash,
    count(DISTINCT odino) FILTER (WHERE fire) AS with_fire,
    count(DISTINCT odino) FILTER (WHERE injured > 0) AS with_injury,
    count(DISTINCT odino) FILTER (WHERE deaths > 0) AS with_death,
    coalesce(sum(injured), 0) AS injured,
    coalesce(sum(deaths), 0) AS deaths
FROM complaint_docs
WHERE make = $make
    AND model_key = $model_key
    AND ($year_from IS NULL OR model_year >= $year_from)
    AND ($year_to IS NULL OR model_year <= $year_to)
    AND ($received_from IS NULL OR received_date >= $received_from)
    AND ($received_to IS NULL OR received_date <= $received_to)
    AND ($component_system IS NULL OR list_contains(component_systems, $component_system))
