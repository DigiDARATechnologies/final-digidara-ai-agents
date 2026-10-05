import { useState, type FormEvent } from "react";
import { Logo } from "./Logo";
import { sendEmailCode, verifyEmailCode, type AuthUser } from "../lib/authApi";

interface Props {
  email: string;
  onVerified: (user: AuthUser) => void;
  onLogout: () => void;
}

/** Shown after a password sign-up (or to an older password account) until
 * the email is verified with the 6-digit code we email. The agents refuse
 * the account on the server until then, so this is the only screen. */
export default function VerifyEmailScreen({ email, onVerified, onLogout }: Props) {
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(`We sent a 6-digit code to ${email}. It expires in 10 minutes.`);
  const [busy, setBusy] = useState(false);
  const [sending, setSending] = useState(false);

  const token = () => localStorage.getItem("digidara_token") || "";

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const digits = code.replace(/\D/g, "");
    if (digits.length !== 6) {
      setError("Enter the 6-digit code from the email.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      onVerified(await verifyEmailCode(token(), digits));
    } catch (err) {
      setError((err as Error).message || "That code didn't work. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    setSending(true);
    setError("");
    try {
      setNotice((await sendEmailCode(token())).message + " Check your spam folder too.");
      setCode("");
    } catch (err) {
      setError((err as Error).message || "We couldn't send the code. Please try again.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="login-overlay">
      <div className="login-card verify-email-card">
        <div className="login-logo">
          <Logo theme="light" size="md" />
        </div>
        <h1>Verify your email</h1>
        <p className="login-sub" role="status">{notice}</p>
        <form onSubmit={handleSubmit}>
          <label className="field">
            <span>Verification code</span>
            <input
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              placeholder="6-digit code"
              autoFocus
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
            />
          </label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button type="submit" className="btn btn-primary btn-full" disabled={busy || code.length !== 6}>
            {busy ? "Verifying…" : "Verify email"}
          </button>
        </form>
        <div className="verify-email-actions">
          <button type="button" className="link-btn" disabled={sending} onClick={() => void resend()}>
            {sending ? "Sending…" : "Send a new code"}
          </button>
          <button type="button" className="link-btn" onClick={onLogout}>Use a different account</button>
        </div>
      </div>
    </div>
  );
}
