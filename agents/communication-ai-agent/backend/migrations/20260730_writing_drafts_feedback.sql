USE communication_module;

ALTER TABLE writing_turns
  ADD COLUMN draft_text TEXT NULL AFTER feedback,
  ADD COLUMN draft_updated_at DATETIME NULL AFTER draft_text;
