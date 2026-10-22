-- One row per complaint (ODINO): the table for per-complaint numbers (injuries, deaths) and for search.
-- any_value is safe because these fields never differ across one ODINO's rows; dq_complaint_attrs_consistent checks it.
CREATE OR REPLACE TABLE complaint_docs AS
WITH narratives AS (
    SELECT odino, any_value(cdescr) AS narrative
    FROM complaints_raw
    WHERE prod_type = 'V' AND odino IS NOT NULL
    GROUP BY odino
)
SELECT
    c.odino,
    any_value(c.make) AS make,
    any_value(c.model) AS model,
    any_value(c.model_key) AS model_key,
    any_value(c.model_year) AS model_year,
    any_value(c.received_date) AS received_date,
    any_value(c.fail_date) AS fail_date,
    any_value(c.crash) AS crash,
    any_value(c.fire) AS fire,
    any_value(c.injured) AS injured,
    any_value(c.deaths) AS deaths,
    any_value(c.miles) AS miles,
    any_value(c.veh_speed) AS veh_speed,
    any_value(c.state) AS state,
    list(DISTINCT c.component ORDER BY c.component) AS components,
    list(DISTINCT c.component_system ORDER BY c.component_system) AS component_systems,
    any_value(n.narrative) AS narrative
FROM complaints AS c
LEFT JOIN narratives AS n USING (odino)
GROUP BY c.odino
