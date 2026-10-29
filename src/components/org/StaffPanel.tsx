import { useCallback, useEffect, useState, type FormEvent } from "react";
import { removeOrgMember, type OrgMember } from "../../lib/learnerApi";
import {
  addStaff, fetchStaff, updateStaff, type AddStaffResult, type ClassOptions, type StaffDetails, type StaffLogin,
} from "../../lib/orgApi";
import ClassSelect from "./ClassSelect";
import StaffStudents from "./StaffStudents";

const ROLE_TEXT: Record<StaffLogin["role"], string> = { owner: "Owner", admin: "Admin", staff: "Staff" };
const EMPTY_DETAILS: StaffDetails = { department: "", degree: "", year: "", section: "", class_head: false };
const DEGREES = ["B.E.", "B.Tech", "B.Sc", "B.Com", "BCA", "BBA", "B.A.", "M.E.", "M.Tech", "M.Sc", "MCA", "MBA", "M.Com", "M.A.", "Diploma", "Ph.D"];
const NO_OPTIONS: ClassOptions = { department: [], year: [], section: [] };

/** "Computer Science · B.E. · 2nd year · A · Class head", or "" when nothing is set. */
function detailsText(s: Partial<StaffDetails>): string {
  return [s.department, s.degree, s.year, s.section && `Section ${s.section}`, s.class_head && "Class head"].filter(Boolean).join(" · ");
}

/** Department, degree, year, section and class head: the same fields for a new or an existing staff login. */
function StaffFields({ value, options, onChange }: { value: StaffDetails; options: ClassOptions; onChange: (next: StaffDetails) => void }) {
  return (
    <div className="org-staff-fields">
      <ClassSelect label="Department" value={value.department} options={options.department}
        onChange={(department) => onChange({ ...value, department })} />
      <label className="field"><span>Degree <small>(optional)</small></span>
        <input list="org-degree-options" value={value.degree} maxLength={80} placeholder="e.g. B.E."
          onChange={(e) => onChange({ ...value, degree: e.target.value })} />
      </label>
      <ClassSelect label="Year" value={value.year} options={options.year} maxLength={40}
        onChange={(year) => onChange({ ...value, year })} />
      <ClassSelect label="Section" value={value.section} options={options.section} maxLength={40}
        onChange={(section) => onChange({ ...value, section })} />
      <label className="org-check">
        <input type="checkbox" checked={value.class_head} onChange={(e) => onChange({ ...value, class_head: e.target.checked })} />
        Class head (in charge of this class)
      </label>
    </div>
  );
}

/** Owners and admins create staff logins. Staff look after the students
 * (student list, approvals, levels, join codes) but cannot add staff or admins.
 * Clicking a staff member's name shows their students and readiness scores. */
export default function StaffPanel({ orgId, options = NO_OPTIONS, onToast, onOpenStudent = () => undefined }: {
  orgId: string; options?: ClassOptions; onToast: (message: string) => void; onOpenStudent?: (member: OrgMember) => void;
}) {
  const [staff, setStaff] = useState<StaffLogin[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [details, setDetails] = useState<StaffDetails>(EMPTY_DETAILS);
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<AddStaffResult | null>(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<{ memberId: string; details: StaffDetails } | null>(null);

  const load = useCallback(() => {
    fetchStaff(orgId).then(setStaff).catch((err) => setError((err as Error).message));
  }, [orgId]);
  useEffect(load, [load]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await addStaff(orgId, { name, email, ...details });
      setCreated(result);
      setName("");
      setEmail("");
      setDetails(EMPTY_DETAILS);
      onToast(`${result.email} can now sign in as staff.`);
      load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function saveEdit() {
    if (!editing) return;
    try {
      await updateStaff(orgId, editing.memberId, editing.details);
      setEditing(null);
      onToast("Staff details saved.");
      load();
    } catch (err) {
      onToast((err as Error).message);
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

  const selected = staff?.find((s) => s.member_id === selectedId);

  return (
    <>
    {selected && (
      <StaffStudents orgId={orgId} person={selected} details={detailsText(selected)} onOpen={onOpenStudent} onClose={() => setSelectedId(null)} />
    )}
    <div className="org-grid-2">
      <datalist id="org-degree-options">{DEGREES.map((d) => <option key={d} value={d} />)}</datalist>
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
          <StaffFields value={details} options={options} onChange={setDetails} />
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
              <li key={s.member_id} className={editing?.memberId === s.member_id ? "org-staff-editing" : undefined}>
                <div>
                  {s.role === "staff" ? (
                    <button type="button" className="org-staff-name" aria-pressed={selectedId === s.member_id}
                      title={`See ${s.name}'s students`} onClick={() => setSelectedId(selectedId === s.member_id ? null : s.member_id)}>
                      {s.name}
                    </button>
                  ) : <b>{s.name}</b>}
                  <span>{s.email}</span>
                  {detailsText(s) && <span className="org-staff-class">{detailsText(s)}</span>}
                  <small>{ROLE_TEXT[s.role]}{s.has_signed_in ? "" : " · not signed in yet"}</small>
                </div>
                {s.role === "staff" && editing?.memberId !== s.member_id && (
                  <div className="org-actions">
                    <button type="button" className="link-btn" onClick={() => setEditing({ memberId: s.member_id, details: {
                      department: s.department ?? "", degree: s.degree ?? "", year: s.year ?? "", section: s.section ?? "",
                      class_head: Boolean(s.class_head) } })}>Edit</button>
                    <button type="button" className="link-btn" onClick={() => void remove(s)}>Remove</button>
                  </div>
                )}
                {editing?.memberId === s.member_id && (
                  <div className="org-staff-edit">
                    <StaffFields value={editing.details} options={options} onChange={(next) => setEditing({ ...editing, details: next })} />
                    <div className="org-actions">
                      <button type="button" className="btn btn-primary btn-sm" onClick={() => void saveEdit()}>Save</button>
                      <button type="button" className="link-btn" onClick={() => setEditing(null)}>Cancel</button>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
    </>
  );
}
