SELECT table_name || '.' || column_name
FROM information_schema.columns
WHERE lower(column_name) IN (SELECT unnest(?::VARCHAR[]))
ORDER BY 1
