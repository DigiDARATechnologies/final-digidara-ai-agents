import { useState, type KeyboardEvent } from "react";

export const MAX_SKILLS = 30;

/** Profile text is lowercase with single spaces, the way the server keeps it. */
export const cleanProfileText = (value: string) => value.toLowerCase().trim().replace(/\s+/g, " ");

/** Lowercase skills without duplicates, in the order they were added. */
export function uniqueSkills(values: string[]): string[] {
  const result: string[] = [];
  for (const value of values) {
    const skill = cleanProfileText(value).slice(0, 60);
    if (skill && !result.includes(skill) && result.length < MAX_SKILLS) result.push(skill);
  }
  return result;
}

interface Props {
  skills: string[];
  onChange: (skills: string[]) => void;
  /** Text typed but not yet turned into a chip, so a submit can include it. */
  draft: string;
  onDraftChange: (draft: string) => void;
  /** Skills the learner can add with one tap (e.g. suggestions for a role). */
  suggestions?: string[];
  suggestionsLabel?: string;
}

/** Skill chips with a free-text box: Enter or a comma adds a skill. */
export default function SkillsInput({ skills, onChange, draft, onDraftChange, suggestions = [], suggestionsLabel = "Add" }: Props) {
  const [focused, setFocused] = useState(false);
  const offered = suggestions.filter((skill) => !skills.includes(cleanProfileText(skill)));

  function add(raw: string) {
    onChange(uniqueSkills([...skills, ...raw.split(",")]));
    onDraftChange("");
  }

  function onKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      add(draft);
    } else if (event.key === "Backspace" && !draft && skills.length) {
      onChange(skills.slice(0, -1));
    }
  }

  return (
    <>
      <div className={`lp-skills${focused ? " focused" : ""}`}
        onClick={(e) => (e.currentTarget.querySelector("input") as HTMLInputElement | null)?.focus()}>
        {skills.map((skill) => (
          <span key={skill} className="lp-chip">
            {skill}
            <button type="button" aria-label={`Remove ${skill}`} onClick={() => onChange(skills.filter((s) => s !== skill))}>×</button>
          </span>
        ))}
        <input value={draft} placeholder={skills.length ? "Add another" : "python, sql, excel…"}
          onChange={(e) => onDraftChange(e.target.value.toLowerCase())} onKeyDown={onKey}
          onFocus={() => setFocused(true)} onBlur={() => { setFocused(false); if (draft) add(draft); }} />
      </div>
      <small className="lp-hint">Press Enter or a comma after each skill.</small>
      {offered.length > 0 && (
        <div className="lp-suggest" aria-label={suggestionsLabel}>
          <span>{suggestionsLabel}:</span>
          {offered.map((skill) => (
            <button key={skill} type="button" className="lp-chip lp-chip-add" onClick={() => onChange(uniqueSkills([...skills, skill]))}>
              + {skill}
            </button>
          ))}
        </div>
      )}
    </>
  );
}
