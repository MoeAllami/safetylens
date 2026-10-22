INSERT INTO doc_embeddings
SELECT odino, text_sha, model, CAST(embedding AS FLOAT[384]) FROM embed_batch
