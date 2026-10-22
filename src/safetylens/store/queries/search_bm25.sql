-- BM25 over narratives, but only for complaints matching the vehicle filter (filter first, then rank).
-- IDF comes from the whole corpus, so a word that is rare everywhere still counts as rare here.
SELECT odino, score
FROM (
    SELECT odino, fts_main_complaint_docs.match_bm25(odino, $query) AS score
    FROM complaint_docs
    WHERE make = $make
        AND model_key = $model_key
        AND ($year_from IS NULL OR model_year >= $year_from)
        AND ($year_to IS NULL OR model_year <= $year_to)
        AND ($received_from IS NULL OR received_date >= $received_from)
        AND ($received_to IS NULL OR received_date <= $received_to)
        AND ($component_system IS NULL OR list_contains(component_systems, $component_system))
)
WHERE score IS NOT NULL
ORDER BY score DESC, odino
LIMIT $k
