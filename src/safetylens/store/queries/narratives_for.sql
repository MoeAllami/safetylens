SELECT odino, coalesce(narrative, '') AS narrative, sha256(coalesce(narrative, '')) AS text_sha
FROM complaint_docs
WHERE odino IN (SELECT unnest(?::VARCHAR[]))
ORDER BY odino
