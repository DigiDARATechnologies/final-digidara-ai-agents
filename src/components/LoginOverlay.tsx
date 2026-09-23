import { useState, type FormEvent } from "react";
import { googleAuthUrl } from "../lib/authApi";
import { Logo } from "./Logo";
import LegalModal from "./LegalModal";

interface LoginOverlayProps {
  onAuthenticate: (
    mode: "login" | "signup",
    details: { name: string; email: string; mobile: string; password: string; consent: boolean },
  ) => Promise<string | null>;
}

const GOOGLE_OAUTH_STATE_KEY = "digidara_google_oauth_state";
// DPDP Act 2023: the OAuth redirect leaves this page before we can send
// consent along with the signup call, so the affirmative checkbox state is
// carried across the redirect the same way `state` is, and read back by
// App.tsx once Google returns control to us.
export const GOOGLE_OAUTH_CONSENT_KEY = "digidara_google_oauth_consent";

function startGoogleSignIn(consent: boolean) {
  const state = crypto.randomUUID();
  sessionStorage.setItem(GOOGLE_OAUTH_STATE_KEY, state);
  sessionStorage.setItem(GOOGLE_OAUTH_CONSENT_KEY, consent ? "1" : "0");
  window.location.href = googleAuthUrl(state);
}

function EyeIcon({ open }: { open: boolean }) {
  return open ? (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  ) : (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M3 3l18 18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M10.6 5.2A11.6 11.6 0 0 1 12 5c7 0 11 7 11 7a14.5 14.5 0 0 1-3.9 4.3M6.6 6.6C3.7 8.4 1 12 1 12s4 7 11 7c1.4 0 2.7-.27 3.9-.73" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function BrandPanel() {
  return (
    <aside className="login-illustration">
      <div className="login-illustration-glow login-illustration-glow--a" aria-hidden="true" />
      <div className="login-illustration-glow login-illustration-glow--b" aria-hidden="true" />

      <div className="login-illustration-brand">
        <Logo theme="dark" size="sm" />
      </div>

      <div className="login-illustration-copy">
        <h2>Your team's AI agent workspace, in one place.</h2>
        <p>Coding practice, communication coaching, aptitude training, resumes and certification — each backed by a specialized agent, all under one account.</p>
      </div>

      <div className="login-mockup" aria-hidden="true">
        <div className="login-mockup-bar">
          <span /><span /><span />
        </div>
        <div className="login-mockup-row">
          <span className="login-mockup-avatar">⚡</span>
          <div className="login-mockup-bubble">Hi! What would you like to work on today?</div>
        </div>
        <div className="login-mockup-row login-mockup-row--user">
          <div className="login-mockup-bubble login-mockup-bubble--user">Help me prep for a system design interview.</div>
        </div>
        <div className="login-mockup-row">
          <span className="login-mockup-avatar">⚡</span>
          <div className="login-mockup-bubble login-mockup-bubble--typing"><i /><i /><i /></div>
        </div>
        <span className="login-badge login-badge--a">🔒 Secure by design</span>
        <span className="login-badge login-badge--b">✓ DPDP-ready privacy</span>
      </div>

      <div className="login-illustration-stats">
        <div><strong>7+</strong><span>Specialized agents</span></div>
        <div><strong>24/7</strong><span>Always available</span></div>
        <div><strong>Bank-grade</strong><span>Session security</span></div>
      </div>
    </aside>
  );
}

export default function LoginOverlay({ onAuthenticate }: LoginOverlayProps) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [mobile, setMobile] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [legalTab, setLegalTab] = useState<"terms" | "privacy" | null>(null);
  const [consent, setConsent] = useState(false);

  function switchMode(next: "login" | "signup") {
    setMode(next);
    setError("");
  }

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
    if (mode === "signup" && !consent) {
      setError("Please accept the Terms of Service and Privacy Policy to continue.");
      return;
    }
    setSubmitting(true);
    const result = await onAuthenticate(mode, { name: trimmedName, email: trimmedEmail, mobile: trimmedMobile, password, consent });
    setSubmitting(false);
    setError(result ?? "");
  }

  function handleGoogleClick() {
    if (mode === "signup" && !consent) {
      setError("Please accept the Terms of Service and Privacy Policy to continue.");
      return;
    }
    startGoogleSignIn(consent);
  }

  return (
    <div className="login-overlay" id="loginOverlay">
      <div className="login-shell">
        <BrandPanel />

        <div className="login-form-panel">
          <div className="login-card">
            <div className="login-logo login-logo--mobile-only">
              <Logo theme="light" size="sm" />
            </div>

            <h1>{mode === "signup" ? "Create your account" : "Welcome back"}</h1>
            <p className="login-sub">
              {mode === "signup"
                ? "Set up your DigiDARA account to start using every specialized agent."
                : "Sign in to continue to your DigiDARA workspace."}
            </p>

            <button type="button" className="btn btn-outline btn-full google-btn" onClick={handleGoogleClick}>
              <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
                <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z" />
                <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18z" />
                <path fill="#FBBC05" d="M3.97 10.72A5.4 5.4 0 0 1 3.68 9c0-.6.1-1.18.29-1.72V4.95H.96A9 9 0 0 0 0 9c0 1.45.35 2.83.96 4.05l3.01-2.33z" />
                <path fill="#EA4335" d="M9 3.58c1.32 0 2.51.45 3.44 1.35l2.59-2.59C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z" />
              </svg>
              Continue with Google
            </button>
            <div className="auth-divider"><span>or continue with email</span></div>

            <form onSubmit={handleSubmit}>
              {mode === "signup" && (
                <label className="field">
                  <span>Full name</span>
                  <input type="text" placeholder="e.g. Priya Sharma" required autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
                </label>
              )}
              <label className="field">
                <span>Email address</span>
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
                <div className="password-field">
                  <input
                    type={showPassword ? "text" : "password"}
                    placeholder={mode === "signup" ? "At least 8 characters" : "Your password"}
                    required
                    minLength={mode === "signup" ? 8 : undefined}
                    autoComplete={mode === "signup" ? "new-password" : "current-password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    className="password-toggle"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    <EyeIcon open={showPassword} />
                  </button>
                </div>
              </label>
              {mode === "signup" && (
                <label className="field">
                  <span>Re-enter password</span>
                  <div className="password-field">
                    <input
                      type={showConfirmPassword ? "text" : "password"}
                      placeholder="Re-enter your password"
                      required
                      minLength={8}
                      autoComplete="new-password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                    />
                    <button
                      type="button"
                      className="password-toggle"
                      onClick={() => setShowConfirmPassword((v) => !v)}
                      aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                    >
                      <EyeIcon open={showConfirmPassword} />
                    </button>
                  </div>
                </label>
              )}

              {mode === "login" && (
                <div className="login-form-row">
                  <a className="link-btn" href="mailto:support@digidaraaiagents.com?subject=Password%20reset%20request">Forgot password?</a>
                </div>
              )}

              {mode === "signup" && (
                <label className="field consent-field">
                  <input
                    type="checkbox"
                    checked={consent}
                    onChange={(e) => setConsent(e.target.checked)}
                  />
                  <span>
                    I have read and agree to the DigiDARA{" "}
                    <button type="button" className="link-btn" onClick={() => setLegalTab("terms")}>Terms of Service</button>
                    {" "}and{" "}
                    <button type="button" className="link-btn" onClick={() => setLegalTab("privacy")}>Privacy Policy</button>,
                    and consent to the collection and use of my personal data as described there.
                  </span>
                </label>
              )}

              {error && <p className="form-error" role="alert">{error}</p>}
              <button type="submit" className="btn btn-primary btn-full" disabled={submitting || (mode === "signup" && !consent)}>
                {submitting ? "Please wait…" : mode === "signup" ? "Create account" : "Log in"}
              </button>
            </form>

            <p className="login-switch">
              {mode === "login" ? (
                <>First time here? <button type="button" className="link-btn" onClick={() => switchMode("signup")}>Sign up instead</button>.</>
              ) : (
                <>Already have an account? <button type="button" className="link-btn" onClick={() => switchMode("login")}>Log in instead</button>.</>
              )}
            </p>

            {mode === "login" && (
              <p className="login-foot">
                By continuing you agree to the DigiDARA{" "}
                <button type="button" className="link-btn" onClick={() => setLegalTab("terms")}>Terms of Service</button>
                {" "}&amp;{" "}
                <button type="button" className="link-btn" onClick={() => setLegalTab("privacy")}>Privacy Policy</button>.
              </p>
            )}
          </div>
        </div>
      </div>
      <LegalModal open={legalTab !== null} initialTab={legalTab ?? "terms"} onClose={() => setLegalTab(null)} />
    </div>
  );
}
