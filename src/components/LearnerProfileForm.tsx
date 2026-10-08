import { useState, type FormEvent, type KeyboardEvent } from "react";
import type { LearnerProfile } from "../lib/learnerApi";

export type ProfileInput = Pick<LearnerProfile, "target_role" | "degree" | "skills" | "experience">;

const ROLE_SUGGESTIONS = [
  "Software Developer", "Full Stack Developer", "Frontend Developer", "Backend Developer", "Data Analyst",
  "Data Scientist", "Machine Learning Engineer", "DevOps Engineer", "Cloud Engineer", "QA / Test Engineer",
  "Business Analyst", "UI/UX Designer", "Cybersecurity Analyst", "Product Manager",
];
const DEGREE_SUGGESTIONS = ["B.E / B.Tech", "B.Sc", "BCA", "B.Com", "BBA", "M.E / M.Tech", "M.Sc", "MCA", "MBA", "Diploma"];
const MAX_SKILLS = 30;

interface Props {
  initial?: Partial<ProfileInput>;
  submitLabel: string;
  busy?: boolean;
  /** Extra fields above the submit button, e.g. consent checkboxes. */
  children?: React.ReactNode;
  canSubmit?: boolean;
  onSubmit: (profile: ProfileInput) => void;
}

/** Target role, degree, skills and experience -- what every agent tailors to. */
export default function LearnerProfileForm({ initial, submitLabel, busy, children, canSubmit = true, onSubmit }: Props) {
  const [targetRole, setTargetRole] = useState(initial?.target_role ?? "");
  const [degree, setDegree] = useState(initial?.degree ?? "");
  const [skills, setSkills] = useState<string[]>(initial?.skills ?? []);
  const [skillDraft, setSkillDraft] = useState("");
  const [experience, setExperience] = useState<ProfileInput["experience"]>(initial?.experience ?? "fresher");
  const [error, setError] = useState("");

  function addSkills(raw: string) {
    const next = [...skills];
    for (const part of raw.split(",")) {
      const skill = part.trim().replace(/\s+/g, " ").slice(0, 60);
      if (skill && !next.some((s) => s.toLowerCase() === skill.toLowerCase()) && next.length < MAX_SKILLS) next.push(skill);
    }
    setSkills(next);
    setSkillDraft("");
  }

  function onSkillKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      addSkills(skillDraft);
    } else if (event.key === "Backspace" && !skillDraft && skills.length) {
      setSkills(skills.slice(0, -1));
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const allSkills = skillDraft.trim() ? [...skills, ...skillDraft.split(",").map((s) => s.trim()).filter(Boolean)] : skills;
    if (targetRole.trim().length < 2) {
      setError("Enter the role you are preparing for.");
      return;
    }
    if (!allSkills.length) {
      setError("Add at least one skill you have or are learning.");
      return;
    }
    setError("");
    onSubmit({ target_role: targetRole.trim(), degree: degree.trim(), skills: allSkills.slice(0, MAX_SKILLS), experience });
  }

  return (
    <form className="lp-form" onSubmit={submit}>
      <label className="field">
        <span>Target role</span>
        <input list="lp-roles" value={targetRole} maxLength={200} placeholder="e.g. Data Analyst" autoFocus
          onChange={(e) => setTargetRole(e.target.value)} />
        <datalist id="lp-roles">{ROLE_SUGGESTIONS.map((role) => <option key={role} value={role} />)}</datalist>
      </label>
      <label className="field">
        <span>Degree</span>
        <input list="lp-degrees" value={degree} maxLength={200} placeholder="e.g. B.E Computer Science"
          onChange={(e) => setDegree(e.target.value)} />
        <datalist id="lp-degrees">{DEGREE_SUGGESTIONS.map((d) => <option key={d} value={d} />)}</datalist>
      </label>
      <div className="field">
        <span>Skills</span>
        <div className="lp-skills" onClick={(e) => (e.currentTarget.querySelector("input") as HTMLInputElement | null)?.focus()}>
          {skills.map((skill) => (
            <span key={skill} className="lp-chip">
              {skill}
              <button type="button" aria-label={`Remove ${skill}`} onClick={() => setSkills(skills.filter((s) => s !== skill))}>×</button>
            </span>
          ))}
          <input value={skillDraft} placeholder={skills.length ? "Add another" : "Python, SQL, Excel…"}
            onChange={(e) => setSkillDraft(e.target.value)} onKeyDown={onSkillKey} onBlur={() => skillDraft && addSkills(skillDraft)} />
        </div>
        <small className="lp-hint">Press Enter or a comma after each skill.</small>
      </div>
      <div className="field">
        <span>Experience</span>
        <div className="lp-segment" role="radiogroup" aria-label="Experience">
          {(["fresher", "experienced"] as const).map((value) => (
            <button key={value} type="button" role="radio" aria-checked={experience === value}
              className={experience === value ? "active" : ""} onClick={() => setExperience(value)}>
              {value === "fresher" ? "Fresher / student" : "Experienced"}
            </button>
          ))}
        </div>
      </div>
      {children}
      {error && <p className="form-error" role="alert">{error}</p>}
      <button type="submit" className="btn btn-primary btn-full" disabled={busy || !canSubmit}>
        {busy ? "Saving…" : submitLabel}
      </button>
    </form>
  );
}
