-- Informational, not a gate: repeated product rows within one complaint, e.g. two tires of the same
-- model under one ODINO. Reported so a jump in this number gets noticed.
SELECT count(*)
FROM (
    SELECT odino, prod_type, maketxt, modeltxt, yeartxt, compdesc
    FROM complaints_raw
    GROUP BY ALL
    HAVING count(*) > 1
)
