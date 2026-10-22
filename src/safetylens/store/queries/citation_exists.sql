-- Which of the given ids exist as a complaint (ODINO) or a recall campaign (CAMPNO).
SELECT odino AS id FROM complaint_docs WHERE odino IN (SELECT unnest($ids::VARCHAR[]))
UNION
SELECT campno AS id FROM recalls WHERE campno IN (SELECT unnest($ids::VARCHAR[]))
