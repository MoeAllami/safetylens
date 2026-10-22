-- Gate D3: a vehicle complaint may list several components, but the same (odino, component) pair
-- twice is a duplicate. Non-vehicle rows (tires, equipment, child seats) are excluded on purpose:
-- one complaint can name the vehicle and a tire under the same component (see dq_product_repeats).
SELECT count(*)
FROM (
    SELECT odino, compdesc
    FROM complaints_raw
    WHERE prod_type = 'V'
    GROUP BY odino, compdesc
    HAVING count(*) > 1
)
