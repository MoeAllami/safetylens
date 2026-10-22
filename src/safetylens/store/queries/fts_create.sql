-- BM25 full-text index over complaint narratives. The index is a snapshot, so it is rebuilt after
-- every `safetylens build` (which replaces complaint_docs).
PRAGMA create_fts_index(
    'complaint_docs', 'odino', 'narrative',
    stemmer = 'porter', stopwords = 'english', lower = 1, strip_accents = 1, overwrite = 1
)
