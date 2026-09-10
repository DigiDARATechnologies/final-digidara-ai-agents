import { useState } from "react";
import { changePassword } from "../../lib/authApi";

/** Self-service password change for the signed-in admin (or any account,
 * technically — the endpoint itself has no admin-only gate — but this is
 * where it's surfaced per the current admin-panel request). Reads the
 * platform bearer token from localStorage directly, same as every other
 * job_agent call in this codebase that isn't routed through gatewayClient.ts. */
export default function AdminChangePassword() {
  const [open, setOpen] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("New password and confirmation do not match.");
      return;
    }
    const token = localStorage.getItem("digidara_token");
    if (!token) {
      setError("Your session has expired. Please log in again.");
      return;
    }
    setSaving(true);
    try {
      await changePassword(token, currentPassword || undefined, newPassword);
      setSuccess("Password updated.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <button className="admin-change-password-toggle" onClick={() => setOpen(true)}>
        Change password
      </button>
    );
  }

  return (
    <form className="admin-change-password" onSubmit={submit}>
      <div className="admin-change-password-head">
        <strong>Change password</strong>
        <button type="button" className="icon-btn" onClick={() => setOpen(false)} aria-label="Close">x</button>
      </div>
      <input
        type="password"
        placeholder="Current password"
        value={currentPassword}
        onChange={(e) => setCurrentPassword(e.target.value)}
        autoComplete="current-password"
      />
      <input
        type="password"
        placeholder="New password (min 8 characters)"
        value={newPassword}
        onChange={(e) => setNewPassword(e.target.value)}
        autoComplete="new-password"
      />
      <input
        type="password"
        placeholder="Confirm new password"
        value={confirmPassword}
        onChange={(e) => setConfirmPassword(e.target.value)}
        autoComplete="new-password"
      />
      {error && <div className="admin-error">{error}</div>}
      {success && <div className="admin-success">{success}</div>}
      <button type="submit" className="btn btn-primary btn-sm btn-full" disabled={saving}>
        {saving ? "Saving…" : "Update password"}
      </button>
    </form>
  );
}

