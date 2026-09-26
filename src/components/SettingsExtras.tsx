import { useState, type FormEvent } from "react";
import type { User } from "../types";
import { changePassword } from "../lib/authApi";
import { ACCENTS, type Accent, type AppearancePrefs, type ThemePref } from "../lib/appearance";

interface AppearanceProps {
  themePref: ThemePref;
  onThemeChange: (pref: ThemePref) => void;
  appearance: AppearancePrefs;
  onAppearanceChange: (next: AppearancePrefs) => void;
  glowOn: boolean;
  onGlowToggle: (on: boolean) => void;
}

const THEME_OPTIONS: { id: ThemePref; label: string; hint: string }[] = [
  { id: "system", label: "System", hint: "Match your device" },
  { id: "dark", label: "Dark", hint: "Pure black" },
  { id: "light", label: "Light", hint: "Bright and clean" },
];

export function AppearanceSettings({ themePref, onThemeChange, appearance, onAppearanceChange, glowOn, onGlowToggle }: AppearanceProps) {
  return (
    <>
      <h2>Appearance</h2>
      <p className="settings-subtitle">Make DigiDARA Agents look and feel the way you like. Changes apply instantly and are remembered on this device.</p>

      <div className="settings-section">
        <div className="setting-row set-stack">
          <div>
            <b>Theme</b>
            <p>Choose dark, light, or follow your device automatically.</p>
          </div>
          <div className="set-seg" role="radiogroup" aria-label="Theme">
            {THEME_OPTIONS.map((o) => (
              <button key={o.id} type="button" role="radio" aria-checked={themePref === o.id} className={themePref === o.id ? "active" : ""} onClick={() => onThemeChange(o.id)}>
                <span>{o.label}</span>
                <small>{o.hint}</small>
              </button>
            ))}
          </div>
        </div>

        <div className="setting-row set-stack">
          <div>
            <b>Accent Colour</b>
            <p>Used for buttons, highlights and links across the app.</p>
          </div>
          <div className="set-swatches" role="radiogroup" aria-label="Accent colour">
            {ACCENTS.map((a) => (
              <button
                key={a.id}
                type="button"
                role="radio"
                aria-checked={appearance.accent === a.id}
                aria-label={a.label}
                title={a.label}
                className={appearance.accent === a.id ? "active" : ""}
                style={{ background: a.color }}
                onClick={() => onAppearanceChange({ ...appearance, accent: a.id as Accent })}
              />
            ))}
          </div>
        </div>

        <div className="setting-row">
          <div>
            <b>Reduce Motion</b>
            <p>Turns off moving effects such as the scrolling agent strip and the animated message-box border.</p>
          </div>
          <label className="switch">
            <input type="checkbox" checked={appearance.reduceMotion} onChange={(e) => onAppearanceChange({ ...appearance, reduceMotion: e.target.checked })} />
            <span className="slider" />
          </label>
        </div>

        <div className="setting-row">
          <div>
            <b>Glow Effects</b>
            <p>Soft glow on cards and buttons.</p>
          </div>
          <label className="switch">
            <input type="checkbox" checked={glowOn} onChange={(e) => onGlowToggle(e.target.checked)} />
            <span className="slider" />
          </label>
        </div>
      </div>
    </>
  );
}

interface SecurityProps {
  user: User;
  onToast: (message: string) => void;
  onLogout?: () => void;
}

export function SecuritySettings({ user, onToast, onLogout }: SecurityProps) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (next.length < 8) return setError("New password must be at least 8 characters.");
    if (next !== confirm) return setError("The new passwords do not match.");
    const token = localStorage.getItem("digidara_token");
    if (!token) return setError("You're not signed in.");
    setBusy(true);
    try {
      await changePassword(token, current || undefined, next);
      setCurrent("");
      setNext("");
      setConfirm("");
      onToast("Password updated.");
    } catch (err) {
      setError((err as Error).message || "Could not update your password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h2>Security</h2>
      <p className="settings-subtitle">Keep your DigiDARA account safe.</p>

      <h3 className="settings-title">Change Password</h3>
      <form className="set-form" onSubmit={submit}>
        <label className="field">
          <span>Current Password</span>
          <input type="password" autoComplete="current-password" placeholder="Leave blank if you only sign in with Google" value={current} onChange={(e) => setCurrent(e.target.value)} />
        </label>
        <label className="field">
          <span>New Password</span>
          <input type="password" autoComplete="new-password" minLength={8} placeholder="At least 8 characters" value={next} onChange={(e) => setNext(e.target.value)} />
        </label>
        <label className="field">
          <span>Re-Enter New Password</span>
          <input type="password" autoComplete="new-password" minLength={8} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        </label>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button type="submit" className="btn btn-primary" disabled={busy || !next || !confirm}>{busy ? "Updating…" : "Update Password"}</button>
      </form>

      <h3 className="settings-title">This Device</h3>
      <div className="settings-section">
        <div className="setting-row">
          <div>
            <b>Signed in as</b>
            <p>{user.email}</p>
          </div>
          {onLogout && <button type="button" className="btn btn-outline" onClick={onLogout}>Log Out</button>}
        </div>
      </div>
    </>
  );
}
