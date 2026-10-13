DROP TABLE IF EXISTS coding_assessment_items;
-- statement-breakpoint
DROP TABLE IF EXISTS coding_assessments;
-- statement-breakpoint
ALTER TABLE coding_problems DROP KEY idx_coding_problems_track, DROP COLUMN track;
