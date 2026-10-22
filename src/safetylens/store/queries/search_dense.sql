-- Cosine similarity between the query vector and each complaint vector, within the vehicle filter.
-- Brute force is fine: one vehicle has at most a few thousand complaints.
SELECT d.odino, array_cosine_similarity(e.embedding, CAST($qvec AS FLOAT[384])) AS score
FROM complaint_docs AS d
JOIN doc_embeddings AS e ON e.odino = d.odino AND e.model = $model
WHERE d.make = $make
    AND d.model_key = $model_key
    AND ($year_from IS NULL OR d.model_year >= $year_from)
    AND ($year_to IS NULL OR d.model_year <= $year_to)
    AND ($received_from IS NULL OR d.received_date >= $received_from)
    AND ($received_to IS NULL OR d.received_date <= $received_to)
    AND ($component_system IS NULL OR list_contains(d.component_systems, $component_system))
ORDER BY score DESC, d.odino
LIMIT $k
