-- Read-only MySQL diagnostics. Run manually in the intended application database.
-- Estimates include application tables/indexes, not provider logs or backups.
SELECT TABLE_NAME, TABLE_ROWS AS estimated_rows,
       ROUND(DATA_LENGTH / 1024 / 1024, 2) AS data_mb,
       ROUND(INDEX_LENGTH / 1024 / 1024, 2) AS index_mb,
       ROUND(DATA_FREE / 1024 / 1024, 2) AS allocated_unused_mb
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
ORDER BY DATA_LENGTH + INDEX_LENGTH DESC;

SELECT COUNT(*) AS evaluations FROM feedback;
SELECT COUNT(*) AS respondents FROM respondents;
SELECT COUNT(*) AS tracked_submissions FROM survey_submissions;
