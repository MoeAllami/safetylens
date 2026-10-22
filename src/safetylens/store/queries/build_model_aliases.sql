-- Map how people (and the NHTSA API) name a model to our canonical model_key.
-- Every known model maps to itself; model_aliases.csv adds curated spellings. Fuzzy matching is Phase 4.
CREATE OR REPLACE TABLE model_aliases AS
SELECT DISTINCT make, model_key AS alias_key, model_key, 'self' AS source
FROM vehicle_models
UNION
SELECT
    upper(trim(make)) AS make,
    regexp_replace(upper(alias), '[\s-]', '', 'g') AS alias_key,
    regexp_replace(upper(model), '[\s-]', '', 'g') AS model_key,
    'curated' AS source
FROM read_csv(?, header = true, all_varchar = true)
