import { useEffect, useRef, useState, type FormEvent } from "react";
import { fileToAvatar, USERNAME_RE, type ProfilePrefs } from "../lib/profilePrefs";

interface Props {
  initialName: string;
  initialUsername: string;
  initialAvatar?: string;
  initial: string;
  onCancel: () => void;
  onSave: (prefs: ProfilePrefs) => void;
}

export default function EditProfileModal({ initialName, initialUsername, initialAvatar, initial, onCancel, onSave }: Props) {
  const [name, setName] = useState(initialName);
  const [username, setUsername] = useState(initialUsername);
  const [avatar, setAvatar] = useState<string | undefined>(initialAvatar);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onCancel();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  async function pick(file: File | undefined) {
    if (!file) return;
    try {
      setAvatar(await fileToAvatar(file));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    const cleanName = name.trim();
    const cleanUser = username.trim();
    if (!cleanName) return setError("Display name can't be empty.");
    if (cleanName.length > 60) return setError("Display name is too long (60 characters max).");
    if (!USERNAME_RE.test(cleanUser)) return setError("Username must be 3 to 30 characters: letters, numbers, dot, dash or underscore.");
    onSave({ displayName: cleanName, username: cleanUser, avatar });
  }

  return (
    <div className="pv-modal-overlay" onClick={(e) => e.target === e.currentTarget && onCancel()}>
      <form className="pv-modal" onSubmit={submit} role="dialog" aria-modal="true" aria-label="Edit profile">
        <h2>Edit profile</h2>

        <div className="pv-modal-avatar">
          <span className="pv-avatar pv-avatar-lg">{avatar ? <img src={avatar} alt="Your profile" /> : initial}</span>
          <button type="button" className="pv-camera" aria-label="Change photo" onClick={() => fileRef.current?.click()}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M4 8.5A1.5 1.5 0 015.5 7h2.2l1.1-1.6A1.5 1.5 0 0110 4.8h4a1.5 1.5 0 011.2.6L16.3 7h2.2A1.5 1.5 0 0120 8.5v9A1.5 1.5 0 0118.5 19h-13A1.5 1.5 0 014 17.5v-9z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
              <circle cx="12" cy="12.5" r="3.2" stroke="currentColor" strokeWidth="1.7" />
            </svg>
          </button>
          <input ref={fileRef} type="file" accept="image/*" hidden onChange={(e) => { void pick(e.target.files?.[0]); e.target.value = ""; }} />
        </div>
        {avatar && (
          <button type="button" className="pv-remove-photo" onClick={() => setAvatar(undefined)}>
            Remove photo
          </button>
        )}

        <label className="pv-field">
          <span>Display name</span>
          <input value={name} maxLength={60} autoFocus onChange={(e) => { setName(e.target.value); setError(""); }} />
        </label>
        <label className="pv-field">
          <span>Username</span>
          <input value={username} maxLength={30} onChange={(e) => { setUsername(e.target.value); setError(""); }} />
        </label>
        {error && <p className="pv-error" role="alert">{error}</p>}
        <p className="pv-modal-note">Profile changes are saved on this device.</p>

        <div className="pv-modal-actions">
          <button type="button" className="pv-btn-ghost" onClick={onCancel}>Cancel</button>
          <button type="submit" className="pv-btn-solid">Save</button>
        </div>
      </form>
    </div>
  );
}
