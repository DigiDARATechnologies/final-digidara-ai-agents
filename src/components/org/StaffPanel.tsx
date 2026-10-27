import { useCallback, useEffect, useState, type FormEvent } from "react";
import { removeOrgMember } from "../../lib/learnerApi";
import { addStaff, fetchStaff, type AddStaffResult, type StaffLogin } from "../../lib/orgApi";

const ROLE_TEXT: Record<StaffLogin["role"], string> = { owner: "Owner", admin: "Admin", staff: "Staff" };

/** Owners and admins create staff logins. Staff look after the students
 * (student list, approvals, levels, join codes) but cannot add staff or admins. */
export default function StaffPanel({ orgId, onToast }: { orgId: string; onToast: (message: string) => void }) {
  const [staff, setStaff] = useState<StaffLogin[] | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<AddStaffResult | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    fetchStaff(orgId).then(setStaff).catch((err) => setError((err as Error).message));
  }, [orgId]);
  useEffect(load, [load]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await addStaff(orgId, { name, email });
      setCreated(result);
      setName("");
      setEmail("");
      onToast(`${result.email} can now sign in as staff.`);
      load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(person: StaffLogin) {
    if (!window.confirm(`Remove ${person.name}'s staff access? Their account stays.`)) return;
    try {
      await removeOrgMember(orgId, person.member_id);
      onToast(`${person.name} no longer has staff access.`);
      load();
    } catch (err) {
      onToast((err as Error).message);
    }
  }

  return (
    <div className="org-grid-2">
      <section className="org-card">
        <h3>Create a staff login</h3>
        <p className="rd-muted">Staff can upload the student list, approve join requests, see students' progress and chats,
          set levels and make join codes. They cannot add staff or admins, or remove members.</p>
        <form onSubmit={submit}>
          <label className="field"><span>Name</span>
            <input value={name} maxLength={255} placeholder="e.g. Priya (Placement cell)" onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="field"><span>Email</span>
            <input type="email" required value={email} maxLength={255} placeholder="priya@college.edu" onChange={(e) => setEmail(e.target.value)} />
          </label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="btn btn-primary btn-full" disabled={busy || !email.trim()}>{busy ? "Creating…" : "Create staff login"}</button>
        </form>
        {created && (
          <div className="og-results">
            <p><b>{created.email}</b>: {created.status === "created" ? "new account" : created.status === "made_staff" ? "changed to staff" : "existing account added as staff"}</p>
            {created.temporary_password && (
              <p>One-time password: <code>{created.temporary_password}</code> <span className="rd-muted">Shown only once. Hand it over; they
                sign in at SkillDARA with this email and password.</span></p>
            )}
          </div>
        )}
      </section>
      <section className="org-card">
        <h3>Who can open this dashboard</h3>
        {staff === null ? <div className="org-skeleton" /> : (
          <ul className="org-code-list">
            {staff.map((s) => (
              <li key={s.member_id}>
                <div><b>{s.name}</b><span>{s.email}</span><small>{ROLE_TEXT[s.role]}{s.has_signed_in ? "" : " · not signed in yet"}</small></div>
                {s.role === "staff" && (
                  <div className="org-actions">
                    <button type="button" className="link-btn" onClick={() => void remove(s)}>Remove</button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
