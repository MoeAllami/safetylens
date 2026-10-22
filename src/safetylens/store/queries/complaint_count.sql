-- Distinct complaints for a vehicle. Never COUNT(*): one complaint has one row per component.
SELECT count(DISTINCT odino) AS complaints
FROM complaints
WHERE make = $make
    AND model_key = $model_key
    AND ($year_from IS NULL OR model_year >= $year_from)
    AND ($year_to IS NULL OR model_year <= $year_to)
    AND ($received_from IS NULL OR received_date >= $received_from)
    AND ($received_to IS NULL OR received_date <= $received_to)
    AND ($component_system IS NULL OR component_system = $component_system)
