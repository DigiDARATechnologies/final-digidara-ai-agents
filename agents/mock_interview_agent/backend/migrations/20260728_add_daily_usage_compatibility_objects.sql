-- Compatibility objects applied to the live database on 2026-07-28.
-- DEFINER is intentionally omitted so this migration remains portable.
USE mock_interview_db;

DROP PROCEDURE IF EXISTS record_answered_question;
DELIMITER $$
CREATE PROCEDURE record_answered_question(IN p_student_id INT)
BEGIN
    INSERT INTO daily_usage (student_id, usage_date, answered_count)
    VALUES (p_student_id, CURDATE(), 1)
    ON DUPLICATE KEY UPDATE answered_count = answered_count + 1;
END$$
DELIMITER ;

DROP FUNCTION IF EXISTS get_remaining_questions;
DELIMITER $$
CREATE FUNCTION get_remaining_questions(p_student_id INT)
RETURNS INT
DETERMINISTIC
BEGIN
    DECLARE v_used INT DEFAULT 0;
    DECLARE v_limit INT DEFAULT 10;

    SELECT answered_count INTO v_used
    FROM daily_usage
    WHERE student_id = p_student_id
      AND usage_date = CURDATE();

    IF v_used IS NULL THEN
        SET v_used = 0;
    END IF;

    RETURN GREATEST(v_limit - v_used, 0);
END$$
DELIMITER ;

CREATE OR REPLACE VIEW today_usage_report AS
SELECT
    s.id AS student_id,
    s.name AS student_name,
    COALESCE(d.answered_count, 0) AS answered_today,
    GREATEST(10 - COALESCE(d.answered_count, 0), 0) AS remaining_today
FROM students s
LEFT JOIN daily_usage d
  ON d.student_id = s.id
 AND d.usage_date = CURDATE();

DROP EVENT IF EXISTS cleanup_old_daily_usage;
CREATE EVENT cleanup_old_daily_usage
ON SCHEDULE EVERY 1 DAY
STARTS '2026-07-29 02:00:00'
ON COMPLETION NOT PRESERVE
ENABLE
DO
    DELETE FROM daily_usage
    WHERE usage_date < CURDATE() - INTERVAL 90 DAY;
