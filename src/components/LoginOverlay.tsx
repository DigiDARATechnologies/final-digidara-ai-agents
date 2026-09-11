import { useState, type FormEvent } from "react";
import { googleAuthUrl } from "../lib/authApi";
import LegalModal from "./LegalModal";

interface LoginOverlayProps {
  onAuthenticate: (
    mode: "login" | "signup",
    details: { name: string; email: string; mobile: string; password: string },
  ) => Promise<string | null>;
}

const GOOGLE_OAUTH_STATE_KEY = "digidara_google_oauth_state";

function startGoogleSignIn() {
  const state = crypto.randomUUID();
  sessionStorage.setItem(GOOGLE_OAUTH_STATE_KEY, state);
  window.location.href = googleAuthUrl(state);
}

export default function LoginOverlay({ onAuthenticate }: LoginOverlayProps) {
  const [mode, setMode] = useState<"login" | "signup">("signup");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [mobile, setMobile] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [legalTab, setLegalTab] = useState<"terms" | "privacy" | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmedName = name.trim();
    const trimmedEmail = email.trim();
    const trimmedMobile = mobile.trim();
    if ((mode === "signup" && (!trimmedName || !trimmedMobile)) || !trimmedEmail || !password) return;
    if (mode === "signup" && password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    setSubmitting(true);
    const result = await onAuthenticate(mode, { name: trimmedName, email: trimmedEmail, mobile: trimmedMobile, password });
    setSubmitting(false);
    setError(result ?? "");
  }

  return (
    <div className="login-overlay" id="loginOverlay">
      <div className="login-card">
        <div className="login-logo">
          <span className="logo-mark">⚡</span>
          <span className="logo-text">
            Digi<b>DARA</b>
          </span>
        </div>
        <h1>{mode === "signup" ? "Create your DigiDARA account" : "Welcome back"}</h1>
        <button type="button" className="btn btn-outline btn-full google-btn" onClick={startGoogleSignIn}>
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
            <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z" />
            <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18z" />
            <path fill="#FBBC05" d="M3.97 10.72A5.4 5.4 0 0 1 3.68 9c0-.6.1-1.18.29-1.72V4.95H.96A9 9 0 0 0 0 9c0 1.45.35 2.83.96 4.05l3.01-2.33z" />
            <path fill="#EA4335" d="M9 3.58c1.32 0 2.51.45 3.44 1.35l2.59-2.59C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z" />
          </svg>
          Continue with Google
        </button>
        <div className="auth-divider"><span>or</span></div>
        <div className="auth-tabs" role="tablist">
          <button type="button" className={mode === "signup" ? "active" : ""} onClick={() => { setMode("signup"); setError(""); }}>Sign up</button>
          <button type="button" className={mode === "login" ? "active" : ""} onClick={() => { setMode("login"); setError(""); }}>Log in</button>
        </div>
        <form onSubmit={handleSubmit}>
          {mode === "signup" && (
            <label className="field">
              <span>Full name</span>
              <input type="text" placeholder="e.g. Priya Sharma" required autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
            </label>
          )}
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              placeholder="you@company.com"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          {mode === "signup" && (
            <label className="field">
              <span>Mobile number</span>
              <input type="tel" placeholder="e.g. +91 98765 43210" required autoComplete="tel" value={mobile} onChange={(e) => setMobile(e.target.value)} />
            </label>
          )}
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              placeholder={mode === "signup" ? "At least 8 characters" : "Your password"}
              required
              minLength={mode === "signup" ? 8 : undefined}
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {mode === "signup" && (
            <label className="field">
              <span>Re-enter password</span>
              <input
                type="password"
                placeholder="Re-enter your password"
                required
                minLength={8}
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
            </label>
          )}
          {error && <p className="form-error" role="alert">{error}</p>}
          <button type="submit" className="btn btn-primary btn-glow btn-full" disabled={submitting}>
            {submitting ? "Please wait…" : mode === "signup" ? "Create account" : "Log in"}
          </button>
        </form>
        <p className="login-foot">
          By continuing you agree to the DigiDARA{" "}
          <button type="button" className="link-btn" onClick={() => setLegalTab("terms")}>Terms of Service</button>
          {" "}&amp;{" "}
          <button type="button" className="link-btn" onClick={() => setLegalTab("privacy")}>Privacy Policy</button>.
        </p>
      </div>
      <LegalModal open={legalTab !== null} initialTab={legalTab ?? "terms"} onClose={() => setLegalTab(null)} />
    </div>
  );
}
