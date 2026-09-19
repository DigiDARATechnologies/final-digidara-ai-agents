-- Retire unrecoverable active sessions that have no question rows.
-- Applied to the live database on 2026-08-01 at 17:26:05 IST; 0 rows required cleanup.
USE mock_interview_db;

UPDATE interviews i
LEFT JOIN interview_details d ON d.interview_id = i.id
SET i.status = 'exited', i.ended_at = COALESCE(i.ended_at, NOW())
WHERE i.status = 'in_progress'
  AND d.id IS NULL;
