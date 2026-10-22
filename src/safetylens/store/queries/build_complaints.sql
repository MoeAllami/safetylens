-- One row per (complaint, component) for vehicle complaints only.
-- Non-vehicle rows (tires, equipment, child seats) stay in complaints_raw: v1 answers vehicle questions.
-- Cleanups from the nhtsa-data skill: YEARTXT 9999 -> NULL, MILES/VEH_SPEED 0 -> NULL (unknown since 2021).
CREATE OR REPLACE TABLE complaints AS
SELECT
    odino,
    upper(trim(maketxt)) AS make,
    upper(trim(modeltxt)) AS model,
    regexp_replace(upper(modeltxt), '[\s-]', '', 'g') AS model_key,
    nullif(yeartxt, 9999) AS model_year,
    compdesc AS component,
    trim(regexp_extract(compdesc, '^[^,:]*')) AS component_system,
    ldate AS received_date,
    faildate AS fail_date,
    crash = 'Y' AS crash,
    fire = 'Y' AS fire,
    injured,
    deaths,
    nullif(miles, 0) AS miles,
    nullif(veh_speed, 0) AS veh_speed,
    state
FROM complaints_raw
WHERE prod_type = 'V' AND odino IS NOT NULL
