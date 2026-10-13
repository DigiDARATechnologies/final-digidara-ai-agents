import { useState, type FormEvent } from "react";
import type { LearnerProfile } from "../lib/learnerApi";
import SkillsInput, { cleanProfileText, uniqueSkills } from "./SkillsInput";

export { cleanProfileText };

export type ProfileInput = Pick<LearnerProfile, "target_role" | "degree" | "skills" | "experience">;

const ROLE_SUGGESTIONS = [
  "software developer", "full stack developer", "frontend developer", "backend developer", "data analyst",
  "data scientist", "machine learning engineer", "devops engineer", "cloud engineer", "qa / test engineer",
  "business analyst", "ui/ux designer", "cybersecurity analyst", "product manager",
];
const DEGREE_SUGGESTIONS = ["b.e / b.tech", "b.sc", "bca", "b.com", "bba", "m.e / m.tech", "m.sc", "mca", "mba", "diploma"];

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
  const [targetRole, setTargetRole] = useState((initial?.target_role ?? "").toLowerCase());
  const [degree, setDegree] = useState((initial?.degree ?? "").toLowerCase());
  const [skills, setSkills] = useState<string[]>(uniqueSkills(initial?.skills ?? []));
  const [skillDraft, setSkillDraft] = useState("");
  const [experience, setExperience] = useState<ProfileInput["experience"]>(initial?.experience ?? "fresher");
  const [error, setError] = useState("");
  const initialRole = cleanProfileText(initial?.target_role ?? "");
  const roleChanged = !!initialRole && cleanProfileText(targetRole).length >= 2 && cleanProfileText(targetRole) !== initialRole;

  function submit(event: FormEvent) {
    event.preventDefault();
    const allSkills = uniqueSkills([...skills, ...skillDraft.split(",")]);
    if (cleanProfileText(targetRole).length < 2) {
      setError("Enter the role you are preparing for.");
      return;
    }
    if (!allSkills.length) {
      setError("Add at least one skill you have or are learning.");
      return;
    }
    setError("");
    onSubmit({ target_role: cleanProfileText(targetRole), degree: cleanProfileText(degree), skills: allSkills, experience });
  }

  return (
    <form className="lp-form" onSubmit={submit}>
      <label className="field">
        <span>Target role</span>
        <input list="lp-roles" value={targetRole} maxLength={200} placeholder="e.g. data analyst" autoFocus
          onChange={(e) => setTargetRole(e.target.value.toLowerCase())} />
        <datalist id="lp-roles">{ROLE_SUGGESTIONS.map((role) => <option key={role} value={role} />)}</datalist>
      </label>
      <label className="field">
        <span>Degree</span>
        <input list="lp-degrees" value={degree} maxLength={200} placeholder="e.g. b.e computer science"
          onChange={(e) => setDegree(e.target.value.toLowerCase())} />
        <datalist id="lp-degrees">{DEGREE_SUGGESTIONS.map((d) => <option key={d} value={d} />)}</datalist>
      </label>
      <div className="field">
        <span>Skills</span>
        {roleChanged ? (
          <p className="lp-role-note">You changed your role to <b>{cleanProfileText(targetRole)}</b>. After you save, you'll choose the skills for it.</p>
        ) : (
          <SkillsInput skills={skills} onChange={setSkills} draft={skillDraft} onDraftChange={setSkillDraft} />
        )}
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
