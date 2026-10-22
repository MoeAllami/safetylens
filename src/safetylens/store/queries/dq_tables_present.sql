SELECT table_name
FROM information_schema.tables
WHERE table_name IN (SELECT unnest(?::VARCHAR[]))
