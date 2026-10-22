-- Every vehicle model seen in complaints or recalls, with its complaint count.
CREATE OR REPLACE TABLE vehicle_models AS
WITH models AS (
    SELECT make, model, model_key FROM complaints
    UNION
    SELECT make, model, model_key FROM recalls
)
SELECT m.make, m.model, m.model_key, count(DISTINCT c.odino) AS complaints
FROM models AS m
LEFT JOIN complaints AS c ON c.make = m.make AND c.model = m.model
GROUP BY m.make, m.model, m.model_key
ORDER BY m.make, m.model
