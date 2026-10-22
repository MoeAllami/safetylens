-- complaint_docs uses any_value(); that is only safe if per-complaint fields agree across rows.
SELECT count(*)
FROM (
    SELECT odino
    FROM complaints
    GROUP BY odino
    HAVING count(DISTINCT (make, model, model_year, received_date, crash, fire, injured, deaths)) > 1
)
