-- Exact alias hit: how the user wrote the model (as a key) -> our canonical model_key.
SELECT DISTINCT model_key FROM model_aliases WHERE make = $make AND alias_key = $alias_key
