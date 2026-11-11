import { useCallback, useEffect, useState, type FormEvent } from "react";
import OrgAssistant from "../org/OrgAssistant";
import OrgDashboard from "../org/OrgDashboard";
import {
  fetchPlatformOrgs, platformCreateOrg, platformDeleteOrg, platformGiveCoins, platformUpdateOrg, type OrgCoins, type PlatformCreateResult, type PlatformOrg,
} from "../../lib/orgApi";
import "../org/Org.css";

const KINDS = [
  { id: "college", label: "College / university" },
  { id: "training_institute", label: "Training institute" },
  { id: "company", label: "Company" },
  { id: "other", label: "Other" },
];
const NO_COINS: OrgCoins = { admin_coins: 0, staff_coins: 0, student_coins: 0 };
const EMPTY_FORM = { name: "", kind: "college", admin_name: "", admin_email: "", member_limit: 1000, ...NO_COINS };
const COIN_FIELDS: { key: keyof OrgCoins; label: string }[] = [
  { key: "admin_coins", label: "For the admin" },
  { key: "staff_coins", label: "For each staff login" },
  { key: "student_coins", label: "For each student" },
];

interface OrgEdit { id: string; name: string; kind: string; member_limit: number; coins: OrgCoins }

function coinsOf(org: PlatformOrg): OrgCoins {
  return { admin_coins: org.admin_coins ?? 0, staff_coins: org.staff_coins ?? 0, student_coins: org.student_coins ?? 0 };
}

/** Coins for the admin, each staff login and each student; each person gets them once, when they get access. */
function CoinFields({ value, onChange }: { value: OrgCoins; onChange: (next: OrgCoins) => void }) {
  return (
    <fieldset className="org-coins">
      <legend>Coins to give <small>(worth the same as a bought coin; given once to each person)</small></legend>
      <div className="org-class-grid three">
        {COIN_FIELDS.map(({ key, label }) => (
          <label key={key} className="field"><span>{label}</span>
            <input type="number" min={0} max={1000000} step={1} value={value[key]}
              onChange={(e) => onChange({ ...value, [key]: Math.max(0, Math.floor(Number(e.target.value) || 0)) })} />
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/** SkillDARA's own admin: every organization is created here, with its first
 * admin login. Any organization's full dashboard opens from the list. */
export default function OrganizationsPanel() {
  const [orgs, setOrgs] = useState<PlatformOrg[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState(EMPTY_FORM);
  const [coinEdit, setCoinEdit] = useState<OrgEdit | null>(null);
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
      setForm(EMPTY_FORM);
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

  function startEdit(org: PlatformOrg) {
    setCoinEdit({ id: org.id, name: org.name, kind: org.kind, member_limit: org.member_limit, coins: coinsOf(org) });
  }

  async function remove(org: PlatformOrg) {
    const typed = window.prompt(
      `Delete ${org.name}?\n\nIts admins, staff and join codes stop working and its ${org.member_count ?? 0} member(s) are released ` +
      "(free to join another organization). Their accounts, coins and every attempt are kept.\n\nType the organization's name to confirm:",
    );
    if (typed === null) return;
    if (typed.trim() !== org.name) {
      setError("The name didn't match, so nothing was deleted.");
      return;
    }
    try {
      const result = await platformDeleteOrg(org.id);
      setToast(`${result.name} deleted. ${result.members_released} member${result.members_released === 1 ? "" : "s"} released.`);
      setCoinEdit(null);
      void load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function saveCoins(org: PlatformOrg, giveNow: boolean) {
    if (!coinEdit) return;
    if (coinEdit.name.trim().length < 2) {
      setError("Enter the organization's name.");
      return;
    }
    try {
      await platformUpdateOrg(org.id, { name: coinEdit.name.trim(), kind: coinEdit.kind, member_limit: coinEdit.member_limit, ...coinEdit.coins });
      if (giveNow) {
        const given = await platformGiveCoins(org.id);
        setToast(given.people ? `${given.coins.toLocaleString()} coins given to ${given.people} ${given.people === 1 ? "person" : "people"}.`
          : "Everyone here already has their coins.");
      } else {
        setToast(`${coinEdit.name.trim()} saved.`);
      }
      setCoinEdit(null);
      void load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (open) {
    return (
      <div className="org-platform-open">
        <OrgDashboard org={{ id: open.id, name: open.name, kind: open.kind, role: "owner" }} onToast={setToast}
          extraTabs={[{ name: "Assistant", render: (filters) => <OrgAssistant orgId={open.id} orgName={open.name} filters={filters} onToast={setToast} /> }]}
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
              <input type="number" min={1} max={100000} value={form.member_limit || ""} disabled={form.member_limit === 0}
                placeholder={form.member_limit === 0 ? "Unlimited" : undefined}
                onChange={(e) => setForm({ ...form, member_limit: Math.max(1, Number(e.target.value) || 1) })} />
            </label>
            <label className="org-check">
              <input type="checkbox" checked={form.member_limit === 0}
                onChange={(e) => setForm({ ...form, member_limit: e.target.checked ? 0 : 1000 })} />
              Unlimited members
            </label>
            <CoinFields value={form} onChange={(coins) => setForm({ ...form, ...coins })} />
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
              {(created.admin.coins ?? 0) > 0 && <span>{created.admin.coins?.toLocaleString()} coins given to the admin.</span>}
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
              <li key={org.id} className={`${org.status === "active" ? "" : "off"}${coinEdit?.id === org.id ? " org-staff-editing" : ""}`}>
                <div>
                  <b>{org.name}</b>
                  <span>{org.member_count ?? 0} / {org.member_limit ? org.member_limit : "Unlimited"} members · {org.active_codes} active code{org.active_codes === 1 ? "" : "s"}</span>
                  <span className="org-staff-class">Coins: admin {coinsOf(org).admin_coins} · staff {coinsOf(org).staff_coins} · student {coinsOf(org).student_coins}</span>
                  <small>{org.admins.map((a) => a.email).join(", ") || "No admin"}{org.status === "suspended" ? " · suspended" : ""}</small>
                </div>
                {coinEdit?.id !== org.id && (
                  <div className="org-actions">
                    <button type="button" className="btn btn-primary btn-sm" onClick={() => setOpen(org)}>Open</button>
                    <button type="button" className="link-btn" onClick={() => startEdit(org)}>Edit</button>
                    <button type="button" className="link-btn" onClick={() => void toggle(org)}>{org.status === "active" ? "Suspend" : "Reactivate"}</button>
                    <button type="button" className="link-btn org-delete-link" onClick={() => void remove(org)}>Delete</button>
                  </div>
                )}
                {coinEdit?.id === org.id && (
                  <div className="org-staff-edit">
                    <label className="field"><span>Organization name</span>
                      <input value={coinEdit.name} required minLength={2} maxLength={255} onChange={(e) => setCoinEdit({ ...coinEdit, name: e.target.value })} />
                    </label>
                    <label className="field"><span>Type</span>
                      <select value={coinEdit.kind} onChange={(e) => setCoinEdit({ ...coinEdit, kind: e.target.value })}>
                        {KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}
                      </select>
                    </label>
                    <label className="field"><span>Member limit</span>
                      <input type="number" min={1} max={100000} value={coinEdit.member_limit || ""} disabled={coinEdit.member_limit === 0}
                        placeholder={coinEdit.member_limit === 0 ? "Unlimited" : undefined}
                        onChange={(e) => setCoinEdit({ ...coinEdit, member_limit: Math.max(1, Number(e.target.value) || 1) })} />
                    </label>
                    <label className="org-check">
                      <input type="checkbox" checked={coinEdit.member_limit === 0}
                        onChange={(e) => setCoinEdit({ ...coinEdit, member_limit: e.target.checked ? 0 : Math.max(1000, org.member_count ?? 0) })} />
                      Unlimited members
                    </label>
                    <CoinFields value={coinEdit.coins} onChange={(coins) => setCoinEdit({ ...coinEdit, coins })} />
                    <p className="rd-muted">New coin amounts apply to people who join from now on. "Save and give now" also gives them to everyone
                      already here who has not had coins for their role yet; nobody gets them twice.</p>
                    <div className="org-actions">
                      <button type="button" className="btn btn-primary btn-sm" onClick={() => void saveCoins(org, false)}>Save</button>
                      <button type="button" className="btn btn-outline btn-sm" onClick={() => void saveCoins(org, true)}>Save and give now</button>
                      <button type="button" className="link-btn" onClick={() => setCoinEdit(null)}>Cancel</button>
                    </div>
                  </div>
                )}
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
