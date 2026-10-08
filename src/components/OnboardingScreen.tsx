import { useState } from "react";
import { Logo } from "./Logo";
import LegalModal from "./LegalModal";
import LearnerProfileForm, { type ProfileInput } from "./LearnerProfileForm";
import { acceptConsent, saveLearnerProfile, type LearnerSummary } from "../lib/learnerApi";

interface Props {
  name: string;
  summary: LearnerSummary;
  onDone: (summary: LearnerSummary) => void;
  onLogout: () => void;
}

/** Shown once, right after sign-up (and email verification): what the learner
 * is preparing for. Every agent uses this, and every agent starts at the
 * Beginner level. An account an organization created also gives its own
 * consent here, and chooses whether the organization may see its progress. */
export default function OnboardingScreen({ name, summary, onDone, onLogout }: Props) {
  const [legalTab, setLegalTab] = useState<"terms" | "privacy" | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [consent, setConsent] = useState(!summary.consent_required);
  const membership = summary.membership;
  const [share, setShare] = useState(membership?.progress_shared ?? true);
  const firstName = name.split(" ")[0] || "there";

  async function submit(profile: ProfileInput) {
    setBusy(true);
    setError("");
    try {
      if (summary.consent_required || (membership && share !== membership.progress_shared)) {
        await acceptConsent(membership ? share : null);
      }
      onDone(await saveLearnerProfile(profile));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-overlay">
      <div className="login-card lp-card">
        <div className="login-logo"><Logo theme="light" size="md" /></div>
        <h1>Welcome, {firstName}</h1>
        <p className="login-sub">
          Tell us what you are preparing for. Every agent — interviews, coding, aptitude, communication, resume and
          jobs — uses this, and you start at the <b>Beginner</b> level everywhere.
        </p>
        {membership && (
          <p className="lp-org-note">You were added by <b>{membership.organization.name}</b>.</p>
        )}
        <LearnerProfileForm submitLabel="Start learning" busy={busy} canSubmit={consent} onSubmit={(p) => void submit(p)}>
          {summary.consent_required && (
            <label className="lp-check">
              <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
              <span>
                I agree to the{" "}
                <button type="button" className="link-btn" onClick={() => setLegalTab("privacy")}>Privacy Policy</button>{" "}
                and{" "}
                <button type="button" className="link-btn" onClick={() => setLegalTab("terms")}>Terms of Service</button>.
              </span>
            </label>
          )}
          {membership && (
            <label className="lp-check">
              <input type="checkbox" checked={share} onChange={(e) => setShare(e.target.checked)} />
              <span>Let {membership.organization.name} see my job readiness and levels. You can change this later.</span>
            </label>
          )}
        </LearnerProfileForm>
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="verify-email-actions">
          <span />
          <button type="button" className="link-btn" onClick={onLogout}>Use a different account</button>
        </div>
      </div>
      <LegalModal open={legalTab !== null} initialTab={legalTab ?? "terms"} onClose={() => setLegalTab(null)} />
    </div>
  );
}
