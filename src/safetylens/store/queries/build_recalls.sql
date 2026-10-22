-- Vehicle recalls, one row per (campaign, vehicle, component). The raw file repeats rows per
-- manufacturer part; those columns are dropped so DISTINCT collapses them. Count with COUNT(DISTINCT campno).
CREATE OR REPLACE TABLE recalls AS
SELECT DISTINCT
    campno,
    upper(trim(maketxt)) AS make,
    upper(trim(modeltxt)) AS model,
    regexp_replace(upper(modeltxt), '[\s-]', '', 'g') AS model_key,
    nullif(yeartxt, 9999) AS model_year,
    compname AS component,
    trim(regexp_extract(compname, '^[^,:]*')) AS component_system,
    mfgname AS manufacturer,
    rcdate AS report_date,
    odate AS owner_notice_date,
    potaff AS potentially_affected,
    desc_defect AS defect_summary,
    consequence_defect AS consequence,
    corrective_action AS remedy,
    coalesce(upper(do_not_drive) = 'YES', false) AS do_not_drive,
    coalesce(upper(park_outside) = 'YES', false) AS park_outside
FROM recalls_raw
WHERE rcltypecd = 'V' AND campno IS NOT NULL
