-- One complaint for its record page. Only columns kept at ingest exist here (no VIN, city, dealer, operator).
SELECT
    odino,
    make,
    model,
    model_year,
    received_date,
    fail_date,
    crash,
    fire,
    injured,
    deaths,
    miles,
    veh_speed,
    state,
    components,
    narrative
FROM complaint_docs
WHERE odino = $odino
