-- Drop stale vectors for the complaints about to be (re-)embedded; embed_batch is a registered Arrow table.
DELETE FROM doc_embeddings WHERE odino IN (SELECT odino FROM embed_batch)
