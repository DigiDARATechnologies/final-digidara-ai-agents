import { useState, type FormEvent } from "react";
import ClassSelect from "./ClassSelect";
import { orgSharingNotice } from "../../lib/orgConsent";
import { CLASS_KINDS, CLASS_LABELS, joinWithClass, previewJoinCode, type ClassFields, type JoinPreview } from "../../lib/orgApi";
import { fetchLearnerSummary, type Membership } from "../../lib/learnerApi";

interface Props {
  onJoined: (membership: Membership) => void;
  onToast: (message: string) => void;
}

/** Step 1: type the code. Step 2: see the organization, the class the code
 * places you in (or pick one), the consent notice, and join. */
export default function JoinOrganization({ onJoined, onToast }: Props) {
  const [code, setCode] = useState("");
  const [preview, setPreview] = useState<JoinPreview | null>(null);
  const [fields, setFields] = useState<ClassFields>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function lookUp(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setPreview(await previewJoinCode(code));
      setFields({});
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function join() {
    if (!preview) return;
    setBusy(true);
    setError("");
    try {
      await joinWithClass(code, fields);
      const summary = await fetchLearnerSummary();
      if (summary.membership) onJoined(summary.membership);
      onToast(`You joined ${preview.organization.name}.`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="org-join">
      <div className="org-join-hero">
        <span className="org-badge">For students</span>
        <h1>Join your college or company</h1>
        <p>Your organization gives you an 8-character code. Joining lets your trainers follow your progress and help you
          get job-ready faster.</p>
      </div>
      <div className="rd-panel org-join-card">
        {!preview ? (
          <form onSubmit={lookUp}>
            <label className="field"><span>Join code</span>
              <input value={code} maxLength={16} required autoFocus placeholder="ABCD2345" className="og-code-input"
                onChange={(e) => setCode(e.target.value.toUpperCase().replace(/\s/g, ""))} />
            </label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="btn btn-primary btn-full" disabled={busy || code.trim().length < 4}>
              {busy ? "Checking…" : "Continue"}
            </button>
          </form>
        ) : (
          <div>
            <div className="org-join-org">
              <span className="org-avatar" aria-hidden="true">{preview.organization.name.slice(0, 1).toUpperCase()}</span>
              <div>
                <b>{preview.organization.name}</b>
                <span>Code {code} · {preview.code.label}</span>
              </div>
              <button type="button" className="link-btn" onClick={() => { setPreview(null); setError(""); }}>Change</button>
            </div>
            <div className="org-join-class">
              {CLASS_KINDS.map((kind) => preview.code[kind] ? (
                <div key={kind} className="field org-fixed-class">
                  <span>{CLASS_LABELS[kind]}</span>
                  <b>{preview.code[kind]}</b>
                </div>
              ) : (
                <ClassSelect key={kind} label={CLASS_LABELS[kind]} value={fields[kind] ?? ""} options={preview.options[kind]}
                  maxLength={kind === "department" ? 120 : 40}
                  onChange={(value) => setFields((current) => ({ ...current, [kind]: value || null }))} />
              ))}
            </div>
            <p className="og-consent">{orgSharingNotice(preview.organization.name)} Joining means you agree to this.</p>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button type="button" className="btn btn-primary btn-full" disabled={busy} onClick={() => void join()}>
              {busy ? "Joining…" : `Join ${preview.organization.name}`}
            </button>
          </div>
        )}
      </div>
      <p className="org-join-foot rd-muted">Is your college not on DigiDARA yet? Ask them to contact DigiDARA to set it up.</p>
    </div>
  );
}
