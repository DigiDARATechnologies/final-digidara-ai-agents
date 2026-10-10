import { Fragment, useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { ScoreRing } from "./ReadinessView";
import { parseMemberLines } from "../lib/memberImport";
import {
  BAND_TONE,
  LEVEL_IDS,
  LEVEL_LABELS,
  addOrgMembers,
  createOrganization,
  fetchOrgMembers,
  fetchOrgSummary,
  joinOrganization,
  leaveOrganization,
  refreshMemberReadiness,
  removeOrgMember,
  rotateJoinCode,
  setMemberLevel,
  setProgressSharing,
  updateOrgMember,
  type AddMemberResult,
  type Band,
  type LearnerSummary,
  type LevelId,
  type MemberReadiness,
  type Membership,
  type OrgMember,
  type OrgSummary,
} from "../lib/learnerApi";

interface Props {
  summary: LearnerSummary;
  onSummaryChange: (summary: LearnerSummary) => void;
  onBack: () => void;
  onToast: (message: string) => void;
}

const KINDS = [
  { id: "college", label: "College / university" },
  { id: "training_institute", label: "Training institute" },
  { id: "company", label: "Company" },
  { id: "other", label: "Other" },
];
const BAND_ORDER: Band[] = ["job_ready", "almost_ready", "developing", "not_ready", "not_started"];
const STATUS_TEXT: Record<AddMemberResult["status"], string> = {
  created: "Account created",
  attached: "Existing account added",
  invalid_email: "Not a valid email",
  limit_reached: "Member limit reached",
  already_in_organization: "Already a member",
  in_another_organization: "In another organization",
};

function downloadCsv(filename: string, rows: string[][]) {
  const csv = rows.map((row) => row.map((cell) => `"${(cell ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function Start({ onMembership, onToast }: { onMembership: (m: Membership) => void; onToast: (m: string) => void }) {
  const [name, setName] = useState("");
  const [kind, setKind] = useState("college");
  const [code, setCode] = useState("");
  const [share, setShare] = useState(true);
  const [busy, setBusy] = useState<"create" | "join" | null>(null);

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy("create");
    try {
      onMembership(await createOrganization(name.trim(), kind));
      onToast("Organization registered. Share the join code with your learners.");
    } catch (err) {
      onToast((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function join(event: FormEvent) {
    event.preventDefault();
    setBusy("join");
    try {
      const membership = await joinOrganization(code.trim(), share);
      onMembership(membership);
      onToast(`You joined ${membership.organization.name}.`);
    } catch (err) {
      onToast((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="og-start">
      <form className="rd-panel" onSubmit={create}>
        <h2>Register your organization</h2>
        <p className="rd-muted">For colleges, institutes and companies: add learners, set their levels and follow their job readiness.</p>
        <label className="field"><span>Organization name</span>
          <input value={name} minLength={2} maxLength={255} required placeholder="e.g. ABC Engineering College" onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="field"><span>Type</span>
          <select value={kind} onChange={(e) => setKind(e.target.value)}>{KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}</select>
        </label>
        <button className="btn btn-primary btn-full" disabled={busy !== null || name.trim().length < 2}>
          {busy === "create" ? "Registering…" : "Register organization"}
        </button>
      </form>
      <form className="rd-panel" onSubmit={join}>
        <h2>Join with a code</h2>
        <p className="rd-muted">Your college or company gives you an 8-character join code.</p>
        <label className="field"><span>Join code</span>
          <input value={code} maxLength={16} required placeholder="ABCD2345" className="og-code-input" onChange={(e) => setCode(e.target.value.toUpperCase())} />
        </label>
        <label className="lp-check">
          <input type="checkbox" checked={share} onChange={(e) => setShare(e.target.checked)} />
          <span>Let the organization see my job readiness and levels.</span>
        </label>
        <button className="btn btn-outline btn-full" disabled={busy !== null || code.trim().length < 4}>
          {busy === "join" ? "Joining…" : "Join organization"}
        </button>
      </form>
    </div>
  );
}

function MemberRow({ member, orgId, isOwner, summary, onChanged, onToast }: {
  member: OrgMember; orgId: string; isOwner: boolean; summary: OrgSummary;
  onChanged: () => void; onToast: (m: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const readiness = member.readiness;

  async function run(action: () => Promise<unknown>, message: string) {
    setBusy(true);
    try {
      await action();
      onToast(message);
      onChanged();
    } catch (err) {
      onToast((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Fragment>
      <tr className={open ? "open" : ""}>
        <td>
          <button type="button" className="og-name" onClick={() => setOpen(!open)} aria-expanded={open}>
            <b>{member.name}</b><span>{member.email}</span>
          </button>
        </td>
        <td>{member.external_id || "—"}</td>
        <td>{member.role === "member" ? "Learner" : member.role === "owner" ? "Owner" : "Admin"}</td>
        <td>
          {!member.progress_shared ? <span className="rd-muted">{member.has_signed_in ? "Not shared" : "Not signed in yet"}</span>
            : readiness ? (
              <span className={`og-band tone-${BAND_TONE[readiness.band]}`}>
                {readiness.overall === null ? "–" : Math.round(readiness.overall)} · {readiness.band_label}
              </span>
            ) : <span className="rd-muted">Not checked yet</span>}
        </td>
        <td className="og-levels-cell">
          {member.levels && Object.entries(member.levels).map(([agent, level]) => (
            <span key={agent} className={`og-lv lv-${level}`} title={`${summary.agent_labels[agent] ?? agent}: ${LEVEL_LABELS[level]}`}>
              {LEVEL_LABELS[level][0]}
            </span>
          ))}
        </td>
      </tr>
      {open && (
        <tr className="og-detail">
          <td colSpan={5}>
            {member.progress_shared ? (
              <div className="og-detail-grid">
                <div>
                  <h4>Levels</h4>
                  {Object.entries(member.levels ?? {}).map(([agent, level]) => (
                    <label key={agent} className="og-level-row">
                      <span>{summary.agent_labels[agent] ?? agent}</span>
                      <select value={level} disabled={busy} onChange={(e) => void run(
                        () => setMemberLevel(orgId, member.member_id, agent, e.target.value as LevelId),
                        `${member.name}: ${summary.agent_labels[agent] ?? agent} set to ${LEVEL_LABELS[e.target.value as LevelId]}.`,
                      )}>
                        {LEVEL_IDS.map((id) => <option key={id} value={id}>{LEVEL_LABELS[id]}</option>)}
                      </select>
                      {readiness?.areas[agent]?.score != null && <small>{Math.round(readiness.areas[agent].score as number)}/100</small>}
                      {readiness?.areas[agent] && <LevelSteps area={readiness.areas[agent]} current={level} />}
                    </label>
                  ))}
                </div>
                <div>
                  <h4>Profile</h4>
                  <p>{member.profile?.target_role || "No target role yet"}{member.profile?.degree ? ` · ${member.profile.degree}` : ""}</p>
                  <div className="rd-chips">{member.profile?.skills.map((s) => <span key={s} className="lp-chip">{s}</span>)}</div>
                  {readiness && <p className="rd-muted">Checked {new Date(`${readiness.computed_at}Z`).toLocaleString()}</p>}
                </div>
              </div>
            ) : <p className="rd-muted">This learner has not agreed to share their progress, so only their name is visible.</p>}
            <div className="og-detail-actions">
              {member.progress_shared && (
                <button className="btn btn-outline btn-sm" disabled={busy}
                  onClick={() => void run(() => refreshMemberReadiness(orgId, member.member_id), `Readiness checked for ${member.name}.`)}>
                  Check readiness now
                </button>
              )}
              {isOwner && member.role !== "owner" && (
                <button className="btn btn-outline btn-sm" disabled={busy}
                  onClick={() => void run(() => updateOrgMember(orgId, member.member_id, { role: member.role === "admin" ? "member" : "admin" }),
                    member.role === "admin" ? `${member.name} is now a learner.` : `${member.name} is now an admin.`)}>
                  {member.role === "admin" ? "Make learner" : "Make admin"}
                </button>
              )}
              {member.role !== "owner" && (
                <button className="btn btn-outline btn-sm btn-danger" disabled={busy}
                  onClick={() => window.confirm(`Remove ${member.name} from the organization? Their account stays.`) &&
                    void run(() => removeOrgMember(orgId, member.member_id), `${member.name} was removed.`)}>
                  Remove
                </button>
              )}
            </div>
          </td>
        </tr>
      )}
    </Fragment>
  );
}

function Dashboard({ membership, onMembership, onToast }: { membership: Membership; onMembership: (m: Membership | null) => void; onToast: (m: string) => void }) {
  const org = membership.organization;
  const [summary, setSummary] = useState<OrgSummary | null>(null);
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [error, setError] = useState("");
  const [lines, setLines] = useState("");
  const [adding, setAdding] = useState(false);
  const [results, setResults] = useState<AddMemberResult[] | null>(null);
  const [search, setSearch] = useState("");
  const [bandFilter, setBandFilter] = useState<Band | "all">("all");

  const load = useCallback(async () => {
    try {
      const [s, m] = await Promise.all([fetchOrgSummary(org.id), fetchOrgMembers(org.id)]);
      setSummary(s);
      setMembers(m);
      setError("");
    } catch (err) {
      setError((err as Error).message);
    }
  }, [org.id]);

  useEffect(() => { void load(); }, [load]);

  async function add(event: FormEvent) {
    event.preventDefault();
    const rows = parseMemberLines(lines);
    if (!rows.length) return;
    setAdding(true);
    try {
      const { results: added } = await addOrgMembers(org.id, rows);
      setResults(added);
      setLines("");
      void load();
    } catch (err) {
      onToast((err as Error).message);
    } finally {
      setAdding(false);
    }
  }

  async function newCode() {
    if (!window.confirm("Make a new join code? The old code stops working.")) return;
    try {
      onMembership(await rotateJoinCode(org.id));
    } catch (err) {
      onToast((err as Error).message);
    }
  }

  const visible = useMemo(() => members.filter((m) => {
    const text = `${m.name} ${m.email} ${m.external_id ?? ""}`.toLowerCase();
    const band = m.readiness?.band ?? "not_started";
    return text.includes(search.toLowerCase()) && (bandFilter === "all" || (m.progress_shared && band === bandFilter));
  }), [members, search, bandFilter]);

  return (
    <>
      <section className="og-head">
        <div>
          <span className="rd-kicker">{KINDS.find((k) => k.id === org.kind)?.label ?? "Organization"}</span>
          <h1>{org.name}</h1>
        </div>
        {org.join_code && (
          <div className="og-code">
            <span>Join code</span>
            <b>{org.join_code}</b>
            <button type="button" className="link-btn" onClick={() => { void navigator.clipboard?.writeText(org.join_code ?? ""); onToast("Join code copied."); }}>Copy</button>
            {membership.role === "owner" && <button type="button" className="link-btn" onClick={() => void newCode()}>New code</button>}
          </div>
        )}
      </section>

      {error && <p className="form-error" role="alert">{error}</p>}

      {summary && (
        <section className="og-stats">
          <div className="og-stat og-stat-ring">
            <ScoreRing score={summary.average_readiness} band={summary.average_readiness === null ? "not_started"
              : summary.average_readiness >= 80 ? "job_ready" : summary.average_readiness >= 60 ? "almost_ready"
              : summary.average_readiness >= 40 ? "developing" : "not_ready"} size={92} />
            <span>Average readiness</span>
          </div>
          <div className="og-stat"><b>{summary.members}</b><span>Members</span></div>
          <div className="og-stat"><b>{summary.signed_in}</b><span>Signed in</span></div>
          <div className="og-stat"><b>{summary.sharing}</b><span>Sharing progress</span></div>
          <div className="og-bands">
            {BAND_ORDER.map((band) => (
              <button key={band} type="button" className={`og-band tone-${BAND_TONE[band]}${bandFilter === band ? " active" : ""}`}
                onClick={() => setBandFilter(bandFilter === band ? "all" : band)}>
                {summary.band_labels[band]} <b>{summary.bands[band] ?? 0}</b>
              </button>
            ))}
          </div>
        </section>
      )}

      {summary && summary.sharing > 0 && (
        <section className="pv-section">
          <h2>Levels by agent</h2>
          <div className="og-level-table">
            {Object.entries(summary.levels).map(([agent, counts]) => {
              const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1;
              return (
                <div key={agent} className="og-level-bar">
                  <span>{summary.agent_labels[agent] ?? agent}</span>
                  <div>{LEVEL_IDS.map((level) => counts[level] > 0 && (
                    <i key={level} className={`lv-${level}`} style={{ width: `${(counts[level] / total) * 100}%` }}
                      title={`${LEVEL_LABELS[level]}: ${counts[level]}`}>{counts[level]}</i>
                  ))}</div>
                </div>
              );
            })}
          </div>
          <div className="og-legend">{LEVEL_IDS.map((l) => <span key={l}><i className={`lv-${l}`} />{LEVEL_LABELS[l]}</span>)}</div>
        </section>
      )}

      <section className="pv-section">
        <div className="pv-section-head">
          <h2>Members</h2>
          <input className="og-search" placeholder="Search name, email or roll number" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div className="og-table-wrap">
          <table className="og-table">
            <thead><tr><th>Learner</th><th>Roll / ID</th><th>Role</th><th>Readiness</th><th>Levels</th></tr></thead>
            <tbody>
              {summary && visible.map((member) => (
                <MemberRow key={member.member_id} member={member} orgId={org.id} isOwner={membership.role === "owner"}
                  summary={summary} onChanged={() => void load()} onToast={onToast} />
              ))}
              {visible.length === 0 && <tr><td colSpan={5} className="rd-muted">No members match.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <section className="pv-section rd-panel">
        <h2>Add members</h2>
        <p className="rd-muted">One learner per line: <code>name, email, roll number</code>. New accounts get a one-time password to hand
          over; existing DigiDARA accounts are added as they are. Each learner chooses whether to share their progress.</p>
        <form onSubmit={add}>
          <textarea className="og-lines" rows={5} value={lines} placeholder={"Priya Kumar, priya@college.edu, 21CS001\nArun S, arun@college.edu, 21CS002"}
            onChange={(e) => setLines(e.target.value)} />
          <button className="btn btn-primary btn-sm" disabled={adding || !lines.trim()}>{adding ? "Adding…" : "Add members"}</button>
        </form>
        {results && (
          <div className="og-results">
            <table className="og-table">
              <thead><tr><th>Email</th><th>Result</th><th>One-time password</th></tr></thead>
              <tbody>{results.map((r) => (
                <tr key={r.email}><td>{r.email}</td><td>{STATUS_TEXT[r.status]}</td><td><code>{r.temporary_password || "—"}</code></td></tr>
              ))}</tbody>
            </table>
            <div className="og-detail-actions">
              <button className="btn btn-outline btn-sm" onClick={() => downloadCsv(`${org.name}-new-members.csv`,
                [["name", "email", "status", "one_time_password"], ...results.map((r) => [r.name ?? "", r.email, STATUS_TEXT[r.status], r.temporary_password ?? ""])])}>
                Download as CSV
              </button>
              <span className="rd-muted">These passwords are shown only once.</span>
            </div>
          </div>
        )}
      </section>
    </>
  );
}


/** "B 100% ✓ · M 40% · H 0% · P 0%": progress at each level for one agent. */
function LevelSteps({ area, current }: { area: MemberReadiness["areas"][string]; current: LevelId }) {
  const scores = area.level_scores ?? {};
  if (!Object.keys(scores).length) {
    return area.level_progress != null ? <span className="og-steps">{LEVEL_LABELS[current]}: {Math.round(area.level_progress)}% (score)</span> : null;
  }
  return (
    <span className="og-steps">
      {LEVEL_IDS.map((id) => {
        const value = Math.round(scores[id] ?? 0);
        return (
          <b key={id} className={`${id === current ? "now" : ""}${value >= 100 ? " done" : ""}`} title={`${LEVEL_LABELS[id]}: ${value}%`}>
            {LEVEL_LABELS[id][0]} {value}%{value >= 100 ? " ✓" : ""}
          </b>
        );
      })}
    </span>
  );
}

export default function OrganizationView({ summary, onSummaryChange, onBack, onToast }: Props) {
  const membership = summary.membership;
  const setMembership = (next: Membership | null) => onSummaryChange({ ...summary, membership: next });
  const isAdmin = membership && membership.role !== "member";

  async function leave() {
    if (!membership || !window.confirm(`Leave ${membership.organization.name}?`)) return;
    try {
      await leaveOrganization();
      setMembership(null);
      onToast("You left the organization.");
    } catch (err) {
      onToast((err as Error).message);
    }
  }

  async function toggleSharing(share: boolean) {
    try {
      setMembership(await setProgressSharing(share));
    } catch (err) {
      onToast((err as Error).message);
    }
  }

  return (
    <div className="pv-page rd-page">
      <div className="pv-inner og-inner">
        <button className="hp-back" onClick={onBack}>← Back</button>
        {!membership && <Start onMembership={setMembership} onToast={onToast} />}
        {membership && isAdmin && <Dashboard membership={membership} onMembership={setMembership} onToast={onToast} />}
        {membership && !isAdmin && (
          <section className="rd-panel">
            <span className="rd-kicker">Your organization</span>
            <h1 className="og-member-title">{membership.organization.name}</h1>
            <label className="lp-check">
              <input type="checkbox" checked={membership.progress_shared} onChange={(e) => void toggleSharing(e.target.checked)} />
              <span>Let {membership.organization.name} see my job readiness and levels.</span>
            </label>
          </section>
        )}
        {membership && membership.role !== "owner" && (
          <p className="og-leave"><button type="button" className="link-btn" onClick={() => void leave()}>Leave {membership.organization.name}</button></p>
        )}
      </div>
    </div>
  );
}
