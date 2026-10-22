-- One vector per complaint. text_sha records which narrative was embedded, so a changed narrative
-- is re-embedded and an unchanged one never is.
CREATE TABLE IF NOT EXISTS doc_embeddings (
    odino VARCHAR PRIMARY KEY,
    text_sha VARCHAR NOT NULL,
    model VARCHAR NOT NULL,
    embedding FLOAT[384] NOT NULL
)
