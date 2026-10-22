-- Narratives for the retrieved complaints, in the order given.
SELECT d.odino, d.received_date, d.components, coalesce(d.narrative, '') AS narrative
FROM complaint_docs AS d
JOIN (SELECT unnest($odinos::VARCHAR[]) AS odino, generate_subscripts($odinos::VARCHAR[], 1) AS pos) AS w
    USING (odino)
ORDER BY w.pos
