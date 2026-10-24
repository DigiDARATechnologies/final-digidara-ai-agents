import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { BarList, ColumnTrend, LevelStacks } from "./charts";
import ClassSelect from "./ClassSelect";
import StudentDrawer from "./StudentDrawer";
import OrgAssessments from "./OrgAssessments";
import OrgKnowledgeTests from "./OrgKnowledgeTests";
import { ScoreRing } from "../ReadinessView";
import { parseMemberLines } from "../../lib/memberImport";
import { addOrgMembers, BAND_TONE, LEVEL_IDS, LEVEL_LABELS, type AddMemberResult, type Band, type OrgMember } from "../../lib/learnerApi";
import {
  CLASS_KINDS,
  CLASS_LABELS,
  createCode,
  fetchAccessLog,
  fetchAnalytics,
  fetchCodes,
  fetchFilteredMembers,
  fetchOptions,
  setCodeActive,
  type AccessEntry,
  type ClassFields,
  type ClassKind,
  type ClassOptions,
  type JoinCode,
  type LearnerBrief,
  type OrgAnalytics,
  type OrgFilters,
} from "../../lib/orgApi";

export interface OrgRef {
  id: string;
  name: string;
  kind: string;
  role: "owner" | "admin";
}

interface Props {
  org: OrgRef;
  onToast: (message: string) => void;
  /** Extra tabs (the organization assistant) rendered by the parent. */
  extraTabs?: { name: string; render: (filters: OrgFilters) => ReactNode }[];
  headerAction?: ReactNode;
}

const KIND_LABELS: Record<string, string> = {
  college: "College / university", training_institute: "Training institute", company: "Company", other: "Organization",
};
const BAND_ORDER: Band[] = ["job_ready", "almost_ready", "developing", "not_ready", "not_started"];
const STATUS_TEXT: Record<AddMemberResult["status"], string> = {
  created: "Account created", attached: "Existing account added", invalid_email: "Not a valid email",
  limit_reached: "Member limit reached", already_in_organization: "Already a member", in_another_organization: "In another organization",
};
const EMPTY_OPTIONS: ClassOptions = { department: [], year: [], section: [] };

function bandFor(score: number | null): Band {
  if (score === null) return "not_started";
  return score >= 80 ? "job_ready" : score >= 60 ? "almost_ready" : score >= 40 ? "developing" : "not_ready";
}

function ago(iso: string | null | undefined): string {
  if (!iso) return "Never";
  const date = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`);
  const days = Math.floor((Date.now() - date.getTime()) / 86_400_000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 30) return `${days} days ago`;
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

function downloadCsv(filename: string, rows: string[][]) {
  const csv = rows.map((row) => row.map((cell) => `"${(cell ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function Kpi({ value, label, hint }: { value: ReactNode; label: string; hint?: string }) {
  return <div className="org-kpi"><b>{value}</b><span>{label}</span>{hint && <small>{hint}</small>}</div>;
}

function Filters({ filters, setFilters, options, codes, agentLabels }: {
  filters: OrgFilters; setFilters: (f: OrgFilters) => void; options: ClassOptions; codes: JoinCode[]; agentLabels: Record<string, string>;
}) {
  const set = (patch: Partial<OrgFilters>) => setFilters({ ...filters, ...patch });
  const active = Object.values(filters).filter(Boolean).length;
  return (
    <div className="org-filters" role="search">
      <input className="org-search" placeholder="Search name, email or roll number" value={filters.search ?? ""}
        onChange={(e) => set({ search: e.target.value || undefined })} />
      {CLASS_KINDS.map((kind) => (
        <select key={kind} value={filters[kind] ?? ""} aria-label={CLASS_LABELS[kind]} onChange={(e) => set({ [kind]: e.target.value || undefined })}>
          <option value="">All {CLASS_LABELS[kind].toLowerCase()}s</option>
          {options[kind].map((value) => <option key={value} value={value}>{value}</option>)}
        </select>
      ))}
      <select value={filters.code_id ?? ""} aria-label="Join code" onChange={(e) => set({ code_id: e.target.value || undefined })}>
        <option value="">All join codes</option>
        {codes.map((code) => <option key={code.id} value={code.id}>{code.code} · {code.label}</option>)}
      </select>
      <select value={filters.band ?? ""} aria-label="Readiness" onChange={(e) => set({ band: (e.target.value || undefined) as Band | undefined })}>
        <option value="">Any readiness</option>
        {BAND_ORDER.map((band) => <option key={band} value={band}>{band.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase())}</option>)}
      </select>
      <select value={filters.status ?? ""} aria-label="Activity" onChange={(e) => set({ status: (e.target.value || undefined) as OrgFilters["status"] })}>
        <option value="">Any activity</option>
        <option value="active">Active this week</option>
        <option value="inactive">Inactive 14+ days</option>
        <option value="not_signed_in">Not signed in</option>
      </select>
      <select value={filters.agent && filters.level ? `${filters.agent}:${filters.level}` : ""} aria-label="Level"
        onChange={(e) => {
          const [agent, level] = e.target.value.split(":");
          set({ agent: agent || undefined, level: (level || undefined) as OrgFilters["level"] });
        }}>
        <option value="">Any level</option>
        {Object.entries(agentLabels).filter(([agent]) => agent !== "job_agent").flatMap(([agent, label]) =>
          LEVEL_IDS.map((level) => <option key={`${agent}:${level}`} value={`${agent}:${level}`}>{label}: {LEVEL_LABELS[level]}</option>))}
      </select>
      {active > 0 && <button type="button" className="link-btn" onClick={() => setFilters({})}>Clear {active} filter{active > 1 ? "s" : ""}</button>}
    </div>
  );
}

function LearnerList({ title, rows, empty, onOpen }: { title: string; rows: LearnerBrief[]; empty: string; onOpen: (id: string) => void }) {
  return (
    <div className="org-card">
      <h3>{title}</h3>
      {rows.length === 0 ? <p className="rd-muted">{empty}</p> : (
        <ul className="org-people">
          {rows.map((row) => (
            <li key={row.member_id}>
              <button type="button" onClick={() => onOpen(row.member_id)}>
                <span className="org-avatar" aria-hidden="true">{row.name.slice(0, 1).toUpperCase()}</span>
                <span className="org-people-name"><b>{row.name}</b><small>{[row.department, row.year, row.section].filter(Boolean).join(" · ") || row.email}</small></span>
                <span className={`og-band tone-${BAND_TONE[bandFor(row.readiness)]}`}>{row.readiness === null ? "–" : Math.round(row.readiness)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Overview({ analytics, onOpen, onFilter }: { analytics: OrgAnalytics; onOpen: (id: string) => void; onFilter: (f: Partial<OrgFilters>) => void }) {
  const [groupBy, setGroupBy] = useState<ClassKind>("department");
  const t = analytics.totals;
  const bandTotal = BAND_ORDER.reduce((sum, band) => sum + (analytics.bands[band] ?? 0), 0);
  return (
    <div className="org-overview">
      <section className="org-kpis">
        <div className="org-kpi org-kpi-ring">
          <ScoreRing score={t.average_readiness} band={bandFor(t.average_readiness)} size={88} />
          <span>Average job readiness</span>
        </div>
        <Kpi value={t.learners} label="Learners" hint={`${t.sharing} sharing progress`} />
        <Kpi value={t.signed_in} label="Signed in" hint={t.learners ? `${Math.round((t.signed_in / t.learners) * 100)}% of learners` : undefined} />
        <Kpi value={t.active_7d} label="Active this week" />
        <Kpi value={t.inactive_14d} label="Inactive 14+ days" />
      </section>

      <section className="org-card">
        <div className="org-card-head"><h3>Readiness bands</h3><span className="rd-muted">Click a band to filter</span></div>
        <div className="org-bandbar" role="img" aria-label={BAND_ORDER.map((b) => `${analytics.band_labels[b]} ${analytics.bands[b] ?? 0}`).join(", ")}>
          {bandTotal === 0 ? <i className="org-stack-empty" /> : BAND_ORDER.map((band) => (analytics.bands[band] ?? 0) > 0 && (
            <button key={band} type="button" className={`tone-${BAND_TONE[band]}`} style={{ flexGrow: analytics.bands[band] }}
              title={`${analytics.band_labels[band]}: ${analytics.bands[band]}`} onClick={() => onFilter({ band })} />
          ))}
        </div>
        <div className="org-band-legend">
          {BAND_ORDER.map((band) => (
            <button key={band} type="button" className={`og-band tone-${BAND_TONE[band]}`} onClick={() => onFilter({ band })}>
              {analytics.band_labels[band]} <b>{analytics.bands[band] ?? 0}</b>
            </button>
          ))}
        </div>
      </section>

      <div className="org-grid-2">
        <section className="org-card">
          <div className="org-card-head">
            <h3>Readiness by {CLASS_LABELS[groupBy].toLowerCase()}</h3>
            <div className="org-seg">{CLASS_KINDS.map((kind) => (
              <button key={kind} type="button" className={groupBy === kind ? "on" : ""} onClick={() => setGroupBy(kind)}>{CLASS_LABELS[kind]}</button>
            ))}</div>
          </div>
          <BarList max={100} format={(v) => String(Math.round(v))}
            rows={analytics.breakdown[groupBy].map((g) => ({ key: g.name, label: g.name, value: g.average_readiness, note: `${g.learners} learner${g.learners === 1 ? "" : "s"}` }))}
            onSelect={(name) => name !== "Not set" && onFilter({ [groupBy]: name })} />
        </section>
        <section className="org-card">
          <div className="org-card-head"><h3>Active learners</h3><span className="rd-muted">last 14 days</span></div>
          <ColumnTrend label="Active learners per day" points={analytics.active_trend.map((p) => ({ date: p.date, value: p.active_learners }))} />
        </section>
      </div>

      <div className="org-grid-2">
        <section className="org-card">
          <div className="org-card-head"><h3>Agent usage</h3><span className="rd-muted">requests, last 30 days</span></div>
          <BarList rows={Object.entries(analytics.usage_30d).map(([agent, count]) => ({ key: agent, label: analytics.agent_labels[agent] ?? agent, value: count }))} />
        </section>
        <section className="org-card">
          <div className="org-card-head"><h3>Levels by agent</h3></div>
          <LevelStacks labels={analytics.level_labels}
            rows={Object.entries(analytics.levels).filter(([agent]) => agent !== "job_agent")
              .map(([agent, counts]) => ({ key: agent, label: analytics.agent_labels[agent] ?? agent, counts }))} />
        </section>
      </div>

      <div className="org-grid-3">
        <LearnerList title="Top learners" rows={analytics.top} empty="No readiness scores yet." onOpen={onOpen} />
        <LearnerList title="Needs attention" rows={analytics.needs_attention} empty="No readiness scores yet." onOpen={onOpen} />
        <LearnerList title="Inactive 14+ days" rows={analytics.inactive} empty="Everyone has been active recently." onOpen={onOpen} />
      </div>
    </div>
  );
}

function Students({ org, members, analytics, onOpen, onReload, onToast }: {
  org: OrgRef; members: OrgMember[]; analytics: OrgAnalytics | null; onOpen: (id: string) => void; onReload: () => void; onToast: (m: string) => void;
}) {
  const [lines, setLines] = useState("");
  const [adding, setAdding] = useState(false);
  const [results, setResults] = useState<AddMemberResult[] | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const learners = members.filter((m) => m.role === "member");

  async function add(event: FormEvent) {
    event.preventDefault();
    const rows = parseMemberLines(lines);
    if (!rows.length) return;
    setAdding(true);
    try {
      const { results: added } = await addOrgMembers(org.id, rows);
      setResults(added);
      setLines("");
      onReload();
    } catch (err) {
      onToast((err as Error).message);
    } finally {
      setAdding(false);
    }
  }

  function exportCsv() {
    downloadCsv(`${org.name}-learners.csv`, [
      ["name", "email", "roll", "department", "year", "section", "join_code", "readiness", "band", "last_active", "signed_in"],
      ...learners.map((m) => [m.name, m.email, m.external_id ?? "", m.department ?? "", m.year ?? "", m.section ?? "",
        m.join_code?.code ?? "", m.readiness?.overall != null ? String(Math.round(m.readiness.overall)) : "",
        m.readiness?.band_label ?? "", m.last_active_at ?? "", m.has_signed_in ? "yes" : "no"]),
    ]);
  }

  return (
    <div>
      <div className="org-toolbar">
        <span className="rd-muted">{learners.length} learner{learners.length === 1 ? "" : "s"}</span>
        <div className="org-actions">
          <button type="button" className="btn btn-outline btn-sm" onClick={exportCsv} disabled={!learners.length}>Export CSV</button>
          <button type="button" className="btn btn-primary btn-sm" onClick={() => setShowAdd(!showAdd)}>{showAdd ? "Close" : "Add learners"}</button>
        </div>
      </div>
      {showAdd && (
        <section className="org-card">
          <h3>Add learners</h3>
          <p className="rd-muted">One per line: <code>name, email, roll number</code>. New accounts get a one-time password to hand over;
            when they sign in they see what the organization can view and agree to it.</p>
          <form onSubmit={add}>
            <textarea className="og-lines" rows={5} value={lines} placeholder={"Priya Kumar, priya@college.edu, 21CS001\nArun S, arun@college.edu, 21CS002"}
              onChange={(e) => setLines(e.target.value)} />
            <button className="btn btn-primary btn-sm" disabled={adding || !lines.trim()}>{adding ? "Adding…" : "Add"}</button>
          </form>
          {results && (
            <div className="og-results">
              <table className="org-table compact">
                <thead><tr><th>Email</th><th>Result</th><th>One-time password</th></tr></thead>
                <tbody>{results.map((r) => (
                  <tr key={r.email}><td>{r.email}</td><td>{STATUS_TEXT[r.status]}</td><td><code>{r.temporary_password || "—"}</code></td></tr>
                ))}</tbody>
              </table>
              <div className="org-actions">
                <button type="button" className="btn btn-outline btn-sm" onClick={() => downloadCsv(`${org.name}-new-learners.csv`,
                  [["name", "email", "status", "one_time_password"], ...results.map((r) => [r.name ?? "", r.email, STATUS_TEXT[r.status], r.temporary_password ?? ""])])}>
                  Download as CSV
                </button>
                <span className="rd-muted">These passwords are shown only once.</span>
              </div>
            </div>
          )}
        </section>
      )}
      <div className="org-table-wrap">
        <table className="org-table">
          <thead><tr><th>Learner</th><th>Class</th><th>Readiness</th><th>Levels</th><th>Last active</th></tr></thead>
          <tbody>
            {learners.map((m) => (
              <tr key={m.member_id} className="org-row" tabIndex={0} onClick={() => onOpen(m.member_id)}
                onKeyDown={(e) => e.key === "Enter" && onOpen(m.member_id)}>
                <td><div className="org-person"><span className="org-avatar" aria-hidden="true">{m.name.slice(0, 1).toUpperCase()}</span>
                  <span><b>{m.name}</b><small>{m.email}{m.external_id ? ` · ${m.external_id}` : ""}</small></span></div></td>
                <td>{[m.department, m.year, m.section].filter(Boolean).join(" · ") || <span className="rd-muted">—</span>}</td>
                <td>{!m.progress_shared ? <span className="rd-muted">{m.has_signed_in ? "Not shared" : "Not signed in"}</span>
                  : m.readiness ? <span className={`og-band tone-${BAND_TONE[m.readiness.band]}`}>
                    {m.readiness.overall === null ? "–" : Math.round(m.readiness.overall)} · {m.readiness.band_label}</span>
                  : <span className="rd-muted">Not checked</span>}</td>
                <td className="org-levels-cell">{m.levels && Object.entries(m.levels).filter(([a]) => a !== "job_agent").map(([agent, level]) => (
                  <i key={agent} className={`org-lv org-lv-${level}`} title={`${analytics?.agent_labels[agent] ?? agent}: ${LEVEL_LABELS[level]}`}>{LEVEL_LABELS[level][0]}</i>
                ))}</td>
                <td>{ago(m.last_active_at)}</td>
              </tr>
            ))}
            {learners.length === 0 && <tr><td colSpan={5} className="org-empty">No learners match these filters.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Codes({ org, codes, options, onReload, onToast }: { org: OrgRef; codes: JoinCode[]; options: ClassOptions; onReload: () => void; onToast: (m: string) => void }) {
  const [fields, setFields] = useState<ClassFields>({});
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const code = await createCode(org.id, { label, ...fields });
      onToast(`New join code ${code.code} created.`);
      setFields({});
      setLabel("");
      onReload();
    } catch (err) {
      onToast((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function toggle(code: JoinCode) {
    try {
      await setCodeActive(org.id, code.id, !code.active);
      onToast(code.active ? `${code.code} no longer works.` : `${code.code} works again.`);
      onReload();
    } catch (err) {
      onToast((err as Error).message);
    }
  }

  return (
    <div className="org-grid-2 org-codes">
      <section className="org-card">
        <h3>Create a join code</h3>
        <p className="rd-muted">Make one code per class. Everyone who joins with it is placed in that department, year and section.
          Leave them empty for a general code: learners then pick their own.</p>
        <form onSubmit={create}>
          {CLASS_KINDS.map((kind) => (
            <ClassSelect key={kind} label={CLASS_LABELS[kind]} value={fields[kind] ?? ""} options={options[kind]}
              maxLength={kind === "department" ? 120 : 40}
              onChange={(value) => setFields((current) => ({ ...current, [kind]: value || null }))} />
          ))}
          <label className="field"><span>Name <small>(optional)</small></span>
            <input value={label} maxLength={120} placeholder="e.g. 2025 batch" onChange={(e) => setLabel(e.target.value)} />
          </label>
          <button className="btn btn-primary btn-full" disabled={busy}>{busy ? "Creating…" : "Create code"}</button>
        </form>
      </section>
      <section className="org-card">
        <h3>Join codes</h3>
        <ul className="org-code-list">
          {codes.map((code) => (
            <li key={code.id} className={code.active ? "" : "off"}>
              <div>
                <b className="org-code">{code.code}</b>
                <span>{code.label}</span>
                <small>{code.members} joined{code.active ? "" : " · turned off"}</small>
              </div>
              <div className="org-actions">
                <button type="button" className="link-btn" onClick={() => { void navigator.clipboard?.writeText(code.code); onToast(`${code.code} copied.`); }}>Copy</button>
                <button type="button" className="link-btn" onClick={() => void toggle(code)}>{code.active ? "Turn off" : "Turn on"}</button>
              </div>
            </li>
          ))}
          {codes.length === 0 && <li className="org-empty">No codes yet.</li>}
        </ul>
      </section>
    </div>
  );
}

function AccessLog({ entries }: { entries: AccessEntry[] }) {
  return (
    <section className="org-card">
      <div className="org-card-head"><h3>Access log</h3><span className="rd-muted">Who opened a learner's details or chats</span></div>
      <p className="rd-muted">Learners can see this for their own data. It is kept so the organization can show it uses access responsibly.</p>
      <div className="org-table-wrap">
        <table className="org-table compact">
          <thead><tr><th>When</th><th>Who</th><th>Learner</th><th>Opened</th></tr></thead>
          <tbody>
            {entries.map((e, i) => (
              <tr key={i}><td>{e.at ? new Date(`${e.at}Z`).toLocaleString() : "—"}</td><td>{e.viewer}</td><td>{e.subject}</td>
                <td>{e.action === "conversation" ? `Chat: ${e.target}` : e.action === "assistant" ? `Assistant: ${e.target}` : "Details"}</td></tr>
            ))}
            {entries.length === 0 && <tr><td colSpan={4} className="org-empty">Nothing opened yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/** The organization admin's dashboard; DigiDARA's platform admin opens the same one for any organization. */
export default function OrgDashboard({ org, onToast, extraTabs = [], headerAction }: Props) {
  const tabs = useMemo(() => ["Overview", "Students", "Assessments", "Knowledge tests", "Join codes", ...extraTabs.map((t) => t.name), "Access log"], [extraTabs]);
  const [tab, setTab] = useState("Overview");
  // A knowledge test the admin chose to share: preselected on the Assessments tab.
  const [linkTestId, setLinkTestId] = useState<string | null>(null);
  const [filters, setFilters] = useState<OrgFilters>({});
  const [analytics, setAnalytics] = useState<OrgAnalytics | null>(null);
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [codes, setCodes] = useState<JoinCode[]>([]);
  const [options, setOptions] = useState<ClassOptions>(EMPTY_OPTIONS);
  const [log, setLog] = useState<AccessEntry[]>([]);
  const [openId, setOpenId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const loadSetup = useCallback(async () => {
    try {
      const [c, o] = await Promise.all([fetchCodes(org.id), fetchOptions(org.id)]);
      setCodes(c);
      setOptions(o);
    } catch (err) {
      setError((err as Error).message);
    }
  }, [org.id]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [a, m] = await Promise.all([fetchAnalytics(org.id, filters), fetchFilteredMembers(org.id, filters)]);
      setAnalytics(a);
      setMembers(m);
      setError("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [org.id, filters]);

  useEffect(() => { void loadSetup(); }, [loadSetup]);
  useEffect(() => {
    const timer = window.setTimeout(() => void loadData(), filters.search ? 300 : 0);
    return () => window.clearTimeout(timer);
  }, [loadData, filters.search]);
  useEffect(() => {
    if (tab === "Access log") fetchAccessLog(org.id).then(setLog).catch((err) => setError((err as Error).message));
  }, [tab, org.id]);

  const openMember = members.find((m) => m.member_id === openId);
  const extra = extraTabs.find((t) => t.name === tab);

  return (
    <div className="org-dash">
      <header className="org-dash-head">
        <div className="org-dash-title">
          <span className="org-avatar xl" aria-hidden="true">{org.name.slice(0, 1).toUpperCase()}</span>
          <div>
            <span className="rd-kicker">{KIND_LABELS[org.kind] ?? "Organization"} · {org.role === "owner" ? "Owner" : "Admin"}</span>
            <h1>{org.name}</h1>
          </div>
        </div>
        {headerAction}
      </header>

      <nav className="org-tabs" role="tablist">
        {tabs.map((name) => (
          <button key={name} type="button" role="tab" aria-selected={tab === name} className={tab === name ? "on" : ""} onClick={() => setTab(name)}>
            {name}
          </button>
        ))}
      </nav>

      {(tab === "Overview" || tab === "Students" || extra) && (
        <Filters filters={filters} setFilters={setFilters} options={options} codes={codes} agentLabels={analytics?.agent_labels ?? {}} />
      )}
      {error && <p className="form-error" role="alert">{error}</p>}
      {loading && !analytics && <div className="org-skeleton tall" />}

      {tab === "Overview" && analytics && (
        <Overview analytics={analytics} onOpen={setOpenId} onFilter={(patch) => { setFilters({ ...filters, ...patch }); setTab("Students"); }} />
      )}
      {tab === "Students" && (
        <Students org={org} members={members} analytics={analytics} onOpen={setOpenId} onReload={() => void loadData()} onToast={onToast} />
      )}
      {tab === "Assessments" && <OrgAssessments orgId={org.id} onToast={onToast} presetTestId={linkTestId} />}
      {tab === "Knowledge tests" && <OrgKnowledgeTests orgId={org.id} onToast={onToast} onCreateLink={(testId) => { setLinkTestId(testId); setTab("Assessments"); }} />}
      {tab === "Join codes" && <Codes org={org} codes={codes} options={options} onReload={() => void loadSetup()} onToast={onToast} />}
      {tab === "Access log" && <AccessLog entries={log} />}
      {extra && extra.render(filters)}

      {openMember && (
        <StudentDrawer orgId={org.id} member={openMember} isOwner={org.role === "owner"} options={options}
          agentLabels={analytics?.agent_labels ?? {}} onClose={() => setOpenId(null)}
          onChanged={() => { void loadData(); void loadSetup(); }} onToast={onToast} />
      )}
    </div>
  );
}
