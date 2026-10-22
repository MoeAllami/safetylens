-- Candidate models for fuzzy matching: one row per model_key, named by its most-complained spelling.
SELECT model_key, arg_max(model, complaints) AS model, sum(complaints) AS complaints
FROM vehicle_models
WHERE make = $make
GROUP BY model_key
ORDER BY complaints DESC
