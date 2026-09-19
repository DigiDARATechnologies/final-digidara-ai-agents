-- Prevent duplicate question positions within one interview.
-- Applied to the live database on 2026-07-31 at 17:44:58 IST.
USE mock_interview_db;

ALTER TABLE interview_details
  ADD CONSTRAINT uq_interview_question_order
    UNIQUE (interview_id, question_order);
