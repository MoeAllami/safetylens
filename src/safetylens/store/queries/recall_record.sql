-- One recall campaign for its record page; the campaign-level text repeats per vehicle row, so take one copy.
SELECT
    campno,
    any_value(manufacturer) AS manufacturer,
    min(report_date) AS report_date,
    min(owner_notice_date) AS owner_notice_date,
    max(potentially_affected) AS potentially_affected,
    any_value(defect_summary) AS defect_summary,
    any_value(consequence) AS consequence,
    any_value(remedy) AS remedy,
    bool_or(do_not_drive) AS do_not_drive,
    bool_or(park_outside) AS park_outside
FROM recalls
WHERE campno = $campno
GROUP BY campno
