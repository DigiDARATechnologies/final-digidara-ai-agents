import { useState, type FormEvent } from "react";
import { normalizeAuthError, requestPasswordReset, resetPassword } from "../lib/authApi";

interface Props {
  open: boolean;
  initialEmail: string;
  onClose: () => void;
  /** Called after the password is changed, with the email, so the login form can be filled in. */
  onDone: (email: string, message: string) => void;
}

/** Forgot password: email -> 6-digit code sent over SMTP -> new password twice. */
export default function ForgotPasswordModal({ open, initialEmail, onClose, onDone }: Props) {
  const [step, setStep] = useState<"email" | "reset">("email");
  const [email, setEmail] = useState(initialEmail);
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [info, setInfo] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (!open) return null;

  async function sendCode(e?: FormEvent) {
    e?.preventDefault();
    const trimmed = email.trim();
    if (!trimmed) return;
    setBusy(true);
    setError("");
    try {
      const result = await requestPasswordReset(trimmed);
      setInfo(result.message);
      setStep("reset");
    } catch (err) {
      setError(normalizeAuthError(err));
    } finally {
      setBusy(false);
    }
  }

  async function submitReset(e: FormEvent) {
    e.preventDefault();
    if (newPassword.length < 8) {
      setError("Your new password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await resetPassword(email.trim(), code.trim(), newPassword);
      onDone(email.trim(), result.message);
    } catch (err) {
      setError(normalizeAuthError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-overlay open" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal-card forgot-card" role="dialog" aria-modal="true" aria-labelledby="forgotTitle">
        <div className="modal-head">
          <h2 id="forgotTitle" className="forgot-title">Reset your password</h2>
          <button type="button" className="icon-btn" aria-label="Close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          {step === "email" ? (
            <form onSubmit={sendCode}>
              <p className="forgot-sub">Enter your account email and we'll send you a 6-digit code.</p>
              <label className="field">
                <span>Email Address</span>
                <input type="email" required autoFocus autoComplete="email" placeholder="you@company.com" value={email} onChange={(e) => setEmail(e.target.value)} />
              </label>
              {error && <p className="form-error" role="alert">{error}</p>}
              <button type="submit" className="btn btn-primary btn-full" disabled={busy || !email.trim()}>
                {busy ? "Sending…" : "Send OTP"}
              </button>
            </form>
          ) : (
            <form onSubmit={submitReset}>
              {info && <p className="forgot-sub">{info} <strong>{email.trim()}</strong></p>}
              <label className="field">
                <span>OTP</span>
                <input
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  required
                  autoFocus
                  maxLength={6}
                  placeholder="6-digit code"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                />
              </label>
              <label className="field">
                <span>New Password</span>
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  minLength={8}
                  autoComplete="new-password"
                  placeholder="At least 8 characters"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                />
              </label>
              <label className="field">
                <span>Retype New Password</span>
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  minLength={8}
                  autoComplete="new-password"
                  placeholder="Re-enter your new password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
              </label>
              <label className="forgot-show">
                <input type="checkbox" checked={showPassword} onChange={(e) => setShowPassword(e.target.checked)} /> Show passwords
              </label>
              {error && <p className="form-error" role="alert">{error}</p>}
              <button type="submit" className="btn btn-primary btn-full" disabled={busy || code.length !== 6}>
                {busy ? "Please wait…" : "Change Password"}
              </button>
              <p className="forgot-resend">
                Didn't get it?{" "}
                <button type="button" className="link-btn" disabled={busy} onClick={() => void sendCode()}>Send a new code</button>
                {" · "}
                <button type="button" className="link-btn" onClick={() => { setStep("email"); setError(""); setCode(""); }}>Change email</button>
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
