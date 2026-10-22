-- complaint_docs grain: one row per distinct complaint in complaints. 0 means they agree.
SELECT
    (SELECT count(*) FROM complaint_docs)
    - (SELECT count(DISTINCT odino) FROM complaints)
