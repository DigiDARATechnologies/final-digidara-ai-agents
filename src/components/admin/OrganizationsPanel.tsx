import { useCallback, useEffect, useState, type FormEvent } from "react";
import OrgDashboard from "../org/OrgDashboard";
import { fetchPlatformOrgs, platformCreateOrg, platformUpdateOrg, type PlatformCreateResult, type PlatformOrg } from "../../lib/orgApi";
import "../org/Org.css";

const KINDS = [
  { id: "college", label: "College / university" },
  { id: "training_institute", label: "Training institute" },
  { id: "company", label: "Company" },
  { id: "other", label: "Other" },
];

/** DigiDARA's own admin: every organization is created here, with its first
 * admin login. Any organization's full dashboard opens from the list. */
export default function OrganizationsPanel() {
  const [orgs, setOrgs] = useState<PlatformOrg[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ name: "", kind: "college", admin_name: "", admin_email: "", member_limit: 1000 });
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<PlatformCreateResult | null>(null);
  const [open, setOpen] = useState<PlatformOrg | null>(null);
  const [search, setSearch] = useState("");
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    try {
      setOrgs(await fetchPlatformOrgs());
      setError("");
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 2600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      setCreated(await platformCreateOrg(form));
      setForm({ name: "", kind: "college", admin_name: "", admin_email: "", member_limit: 1000 });
      void load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function toggle(org: PlatformOrg) {
    const next = org.status === "active" ? "suspended" : "active";
    if (next === "suspended" && !window.confirm(`Suspend ${org.name}? Its admins and join codes stop working until you reactivate it.`)) return;
    try {
      await platformUpdateOrg(org.id, { status: next });
      setToast(next === "suspended" ? `${org.name} suspended.` : `${org.name} reactivated.`);
      void load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (open) {
    return (
      <div className="org-platform-open">
        <OrgDashboard org={{ id: open.id, name: open.name, kind: open.kind, role: "owner" }} onToast={setToast}
          headerAction={<button type="button" className="btn btn-outline btn-sm" onClick={() => setOpen(null)}>← All organizations</button>} />
        {toast && <div className="org-toast" role="status">{toast}</div>}
      </div>
    );
  }

  const visible = orgs.filter((o) => `${o.name} ${o.admins.map((a) => a.email).join(" ")}`.toLowerCase().includes(search.toLowerCase()));
  const totals = { orgs: orgs.length, members: orgs.reduce((sum, o) => sum + (o.member_count ?? 0), 0), active: orgs.filter((o) => o.status === "active").length };

  return (
    <div className="org-platform">
      {error && <p className="form-error" role="alert">{error}</p>}
      <section className="org-kpis">
        <div className="org-kpi"><b>{totals.orgs}</b><span>Organizations</span></div>
        <div className="org-kpi"><b>{totals.active}</b><span>Active</span></div>
        <div className="org-kpi"><b>{totals.members}</b><span>Members in all</span></div>
      </section>
      <div className="org-grid-2">
        <section className="org-card">
          <h3>Create an organization</h3>
          <p className="rd-muted">Creates the organization and its admin login. A new admin gets a one-time password, shown once here.</p>
          <form onSubmit={create}>
            <label className="field"><span>Organization name</span>
              <input value={form.name} required minLength={2} maxLength={255} placeholder="e.g. ABC Engineering College"
                onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </label>
            <label className="field"><span>Type</span>
              <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
                {KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}
              </select>
            </label>
            <div className="org-class-grid two">
              <label className="field"><span>Admin's name</span>
                <input value={form.admin_name} maxLength={255} placeholder="e.g. Dr. Meena" onChange={(e) => setForm({ ...form, admin_name: e.target.value })} />
              </label>
              <label className="field"><span>Admin's email</span>
                <input type="email" required value={form.admin_email} maxLength={255} placeholder="placement@college.edu"
                  onChange={(e) => setForm({ ...form, admin_email: e.target.value })} />
              </label>
            </div>
            <label className="field"><span>Member limit</span>
              <input type="number" min={1} max={100000} value={form.member_limit}
                onChange={(e) => setForm({ ...form, member_limit: Number(e.target.value) || 1 })} />
            </label>
            <button className="btn btn-primary btn-full" disabled={busy}>{busy ? "Creating…" : "Create organization"}</button>
          </form>
          {created && (
            <div className="org-created" role="status">
              <b>{created.organization.name} is ready.</b>
              <span>Admin login: {created.admin.email}</span>
              {created.admin.temporary_password ? (
                <span>One-time password: <code>{created.admin.temporary_password}</code> <button type="button" className="link-btn"
                  onClick={() => { void navigator.clipboard?.writeText(created.admin.temporary_password ?? ""); setToast("Password copied."); }}>Copy</button></span>
              ) : <span>That account already existed, so it keeps its own password.</span>}
              <span>General join code: <code>{created.organization.join_code}</code></span>
              <small>The password is shown only now. The admin should sign in, verify their email and change it.</small>
            </div>
          )}
        </section>
        <section className="org-card">
          <div className="org-card-head">
            <h3>Organizations</h3>
            <input className="org-search" placeholder="Search name or admin email" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <ul className="org-code-list">
            {visible.map((org) => (
              <li key={org.id} className={org.status === "active" ? "" : "off"}>
                <div>
                  <b>{org.name}</b>
                  <span>{org.member_count ?? 0} / {org.member_limit} members · {org.active_codes} active code{org.active_codes === 1 ? "" : "s"}</span>
                  <small>{org.admins.map((a) => a.email).join(", ") || "No admin"}{org.status === "suspended" ? " · suspended" : ""}</small>
                </div>
                <div className="org-actions">
                  <button type="button" className="btn btn-primary btn-sm" onClick={() => setOpen(org)}>Open</button>
                  <button type="button" className="link-btn" onClick={() => void toggle(org)}>{org.status === "active" ? "Suspend" : "Reactivate"}</button>
                </div>
              </li>
            ))}
            {visible.length === 0 && <li className="org-empty">No organizations yet.</li>}
          </ul>
        </section>
      </div>
      {toast && <div className="org-toast" role="status">{toast}</div>}
    </div>
  );
}
