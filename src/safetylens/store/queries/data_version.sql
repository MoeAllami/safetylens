-- What the cache key depends on: newest complaint, complaint and campaign counts. A rebuild changes it.
SELECT
    (SELECT max(received_date) FROM complaint_docs) AS newest_complaint,
    (SELECT count(*) FROM complaint_docs) AS complaints,
    (SELECT count(DISTINCT campno) FROM recalls) AS campaigns
