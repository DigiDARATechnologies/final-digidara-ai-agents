USE communication_module;

CREATE UNIQUE INDEX uq_pronunciation_daily_user_date_mode_difficulty
ON pronunciation_items (user_id, daily_date, practice_mode, difficulty);
