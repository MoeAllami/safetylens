-- Complaints with no vector yet, or whose narrative or model changed since they were embedded.
SELECT d.odino
FROM complaint_docs AS d
LEFT JOIN doc_embeddings AS e
    ON e.odino = d.odino
    AND e.text_sha = sha256(coalesce(d.narrative, ''))
    AND e.model = $model
WHERE e.odino IS NULL
ORDER BY d.odino
