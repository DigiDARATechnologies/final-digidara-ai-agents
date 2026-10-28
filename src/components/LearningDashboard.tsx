import { useCallback, useEffect, useState } from "react";
import { fetchLearningDashboard, type DashboardStatus, type LearningDashboardData } from "../lib/learnerApi";
import "./LearningDashboard.css";

const VIEW_LABELS: Record<string, string> = {
  me: "My learning", students: "My students", organization: "Organization", platform: "Whole platform",
};
// Fixed order, never cycled (reference categorical palette, light / dark steps in the CSS).
const STATUS_ORDER: DashboardStatus[] = ["submitted", "open", "in_progress", "upcoming", "missed"];
const STATUS_LABELS: Record<DashboardStatus, string> = {
  submitted: "Submitted", open: "Open now", in_progress: "In progress", upcoming: "Upcoming", missed: "Missed",
};
const AGENT_LABELS: Record<string, string> = {
  aptitude_agent: "Aptitude Trainer", codeforge_agent: "Coding Practice", mock_interview_agent: "Mock Interview",
  communication_agent: "Communication Coach", resume_builder_agent: "Resume Builder", capstone_project_agent: "Capstone Project",
  certificate_agent: "AI Certification", job_agent: "Job Agent", boss: "SkillDARA Assistant",
};

function monthLabel(key: string): string {
  const [year, month] = key.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, 1)).toLocaleString(undefined, { month: "short" });
}

function ago(iso: string | null): string {
  if (!iso) return "Not yet";
  const days = Math.floor((Date.now() - new Date(iso.endsWith("Z") ? iso : `${iso}Z`).getTime()) / 86400000);
  return days <= 0 ? "Today" : days === 1 ? "Yesterday" : `${days} days ago`;
}

function Kpi({ label, value, note, progress, target }: { label: string; value: string; note: string; progress?: number | null; target?: number }) {
  return (
    <div className="ld-kpi">
      <span>{label}</span>
      <strong>{value}</strong>
      {progress !== undefined && (
        <div className="ld-progress" role="img" aria-label={`${label}: ${progress ?? 0}%${target ? `, target ${target}%` : ""}`}>
          <i style={{ width: `${Math.max(0, Math.min(100, progress ?? 0))}%` }} />
          {target !== undefined && <b style={{ left: `${target}%` }} />}
        </div>
      )}
      <small>{note}</small>
    </div>
  );
}

/** Two series per month (assigned, attempted): grouped bars on one axis, legend + hover tooltip. */
function MonthlyBars({ rows }: { rows: LearningDashboardData["monthly"] }) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(1, ...rows.flatMap((r) => [r.assigned, r.attempted]));
  const ticks = [0, Math.ceil(max / 2), max];
  return (
    <div className="ld-bars">
      <div className="ld-legend"><span className="s1">Assigned</span><span className="s2">Attempted</span></div>
      <div className="ld-plot" role="img" aria-label="Assessments assigned and attempted per month">
        <div className="ld-axis">{[...ticks].reverse().map((t) => <span key={t}>{t}</span>)}</div>
        <div className="ld-columns">
          {rows.map((row, index) => (
            <div key={row.month} className={`ld-month${hover === index ? " on" : ""}`}
              onMouseEnter={() => setHover(index)} onMouseLeave={() => setHover(null)}>
              <div className="ld-pair">
                <i className="s1" style={{ height: `${(row.assigned / max) * 100}%` }} />
                <i className="s2" style={{ height: `${(row.attempted / max) * 100}%` }} />
              </div>
              <span>{monthLabel(row.month)}</span>
              {hover === index && (
                <div className="ld-tip" role="tooltip">
                  <b>{monthLabel(row.month)} {row.month.slice(0, 4)}</b>
                  <span><i className="s1" />Assigned {row.assigned}</span>
                  <span><i className="s2" />Attempted {row.attempted}</span>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/** One series: agent requests per month. */
function ActivityBars({ rows }: { rows: LearningDashboardData["monthly"] }) {
  const max = Math.max(1, ...rows.map((r) => r.requests));
  return (
    <div className="ld-activity" role="img" aria-label="Agent requests per month">
      {rows.map((row) => (
        <div key={row.month} title={`${monthLabel(row.month)}: ${row.requests} requests`}>
          <i style={{ height: `${(row.requests / max) * 100}%` }} />
          <span>{monthLabel(row.month)}</span>
        </div>
      ))}
    </div>
  );
}

/** Assessment status as a donut: a share of a whole, every slice labelled with its count beside it. */
function StatusDonut({ status }: { status: Record<DashboardStatus, number> }) {
  const total = STATUS_ORDER.reduce((sum, key) => sum + (status[key] ?? 0), 0);
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  return (
    <div className="ld-donut">
      <svg viewBox="0 0 140 140" role="img" aria-label={STATUS_ORDER.map((k) => `${STATUS_LABELS[k]} ${status[k] ?? 0}`).join(", ")}>
        <circle cx="70" cy="70" r={radius} className="ld-donut-track" />
        {total > 0 && STATUS_ORDER.map((key) => {
          const value = status[key] ?? 0;
          if (!value) return null;
          const length = (value / total) * circumference;
          // A 2px surface gap between slices.
          const slice = <circle key={key} cx="70" cy="70" r={radius} className={`ld-slice st-${key}`}
            strokeDasharray={`${Math.max(0, length - 2)} ${circumference}`} strokeDashoffset={-offset} />;
          offset += length;
          return slice;
        })}
        <text x="70" y="66" className="ld-donut-total">{total}</text>
        <text x="70" y="84" className="ld-donut-caption">assessments</text>
      </svg>
      <ul>
        {STATUS_ORDER.map((key) => (
          <li key={key}><i className={`st-${key}`} />{STATUS_LABELS[key]}
            <b>{status[key] ?? 0}</b><small>{total ? `${Math.round(((status[key] ?? 0) / total) * 100)}%` : "0%"}</small></li>
        ))}
      </ul>
    </div>
  );
}

function HBars({ rows, max = 100, format = (v: number) => String(Math.round(v)) }: {
  rows: { key: string; label: string; value: number }[]; max?: number; format?: (v: number) => string;
}) {
  const top = Math.max(max, ...rows.map((r) => r.value));
  return (
    <ul className="ld-hbars">
      {rows.map((row) => (
        <li key={row.key}>
          <span>{row.label}</span>
          <div><i style={{ width: `${(row.value / top) * 100}%` }} /></div>
          <b>{format(row.value)}</b>
        </li>
      ))}
    </ul>
  );
}

/** The learning dashboard: your own learning, or (staff, admins) your students'. */
export default function LearningDashboard({ onBack }: { onBack?: () => void }) {
  const [view, setView] = useState<string | undefined>(undefined);
  const [data, setData] = useState<LearningDashboardData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await fetchLearningDashboard(view));
      setError("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [view]);
  useEffect(() => { void load(); }, [load]);

  const kpis = data?.kpis;
  const group = data && data.view !== "me";
  return (
    <div className="pv-page ld-page">
      <div className="pv-inner ld-inner">
        {onBack && <button className="hp-back" onClick={onBack}>← Back</button>}
        <header className="ld-head">
          <div>
            <span className="ld-kicker">{group ? "Learning overview" : "Your progress"}</span>
            <h1>Learning Dashboard</h1>
            <p>{data ? `${data.label}${group ? ` · ${data.people} learner${data.people === 1 ? "" : "s"}` : ""}` : "Your learning journey at a glance."}</p>
          </div>
          {data && data.views.length > 1 && (
            <div className="ld-switch" role="tablist" aria-label="Dashboard view">
              {data.views.map((value) => (
                <button key={value} type="button" role="tab" aria-selected={data.view === value} className={data.view === value ? "on" : ""}
                  onClick={() => setView(value)}>{VIEW_LABELS[value] ?? value}</button>
              ))}
            </div>
          )}
        </header>

        {error && <p className="form-error" role="alert">{error} <button className="link-btn" onClick={() => void load()}>Retry</button></p>}
        {loading && !data && <div className="ld-skeleton" />}

        {data && kpis && (
          <>
            <section className="ld-kpis">
              <Kpi label={group ? "Average job readiness" : "Job readiness"} value={kpis.readiness === null ? "—" : `${Math.round(kpis.readiness)}`}
                note={kpis.readiness === null ? "Check your job readiness to get a score" : "out of 100"} progress={kpis.readiness} />
              <Kpi label="Assessments" value={String(kpis.assessments)} note={`${kpis.submitted} submitted`}
                progress={kpis.assessments ? (100 * kpis.submitted) / kpis.assessments : 0} />
              <Kpi label="Submission rate" value={kpis.submission_rate === null ? "—" : `${Math.round(kpis.submission_rate)}%`}
                note="Target 85%" progress={kpis.submission_rate} target={85} />
              <Kpi label="Average score" value={kpis.average_score === null ? "—" : `${Math.round(kpis.average_score)}%`}
                note="Target 80%" progress={kpis.average_score} target={80} />
              <Kpi label={group ? `Active in ${kpis.active_days} days` : "Agent requests"}
                value={group ? `${kpis.active_recently} / ${data.people}` : String(kpis.requests_30d)}
                note={group ? "learners using SkillDARA" : "in the last 30 days"} />
            </section>

            <section className="ld-grid">
              <article className="ld-card ld-wide">
                <div className="ld-card-head"><h2>Monthly assessment progress</h2><span>Last 6 months</span></div>
                <MonthlyBars rows={data.monthly} />
              </article>
              <article className="ld-card">
                <div className="ld-card-head"><h2>Assessment status</h2></div>
                <StatusDonut status={data.status} />
              </article>
              <article className="ld-card">
                <div className="ld-card-head"><h2>Agent activity</h2><span>Requests per month</span></div>
                <ActivityBars rows={data.monthly} />
                {data.agents.length > 0 && <HBars rows={data.agents.map((a) => ({ key: a.agent, label: AGENT_LABELS[a.agent] ?? a.agent, value: a.requests }))}
                  max={1} />}
              </article>
              <article className="ld-card">
                <div className="ld-card-head"><h2>Readiness by area</h2><span>out of 100</span></div>
                {data.areas.length ? <HBars rows={data.areas.map((a) => ({ key: a.label, label: a.label, value: a.average }))} />
                  : <p className="ld-empty">No area scores yet.</p>}
              </article>

              {!group && (
                <article className="ld-card ld-wide">
                  <div className="ld-card-head"><h2>Your assessments</h2></div>
                  {data.assessments.length ? (
                    <table className="ld-table">
                      <thead><tr><th>Assessment</th><th>Status</th><th>Score</th><th>Closes</th></tr></thead>
                      <tbody>{data.assessments.map((a) => (
                        <tr key={a.title}><td>{a.title}</td><td><span className={`ld-pill st-${a.status}`}>{STATUS_LABELS[a.status]}</span></td>
                          <td>{a.score === null ? "—" : `${Math.round(a.score)}%`}</td>
                          <td>{a.closes_at ? new Date(`${a.closes_at}Z`).toLocaleDateString() : "—"}</td></tr>
                      ))}</tbody>
                    </table>
                  ) : <p className="ld-empty">No assessments from your organization yet.</p>}
                </article>
              )}

              {group && (
                <article className="ld-card ld-wide">
                  <div className="ld-card-head"><h2>Learners</h2><span>Highest readiness first</span></div>
                  {data.learners.length ? (
                    <table className="ld-table">
                      <thead><tr><th>Learner</th><th>Job readiness</th><th>Assessments</th><th>Last active</th></tr></thead>
                      <tbody>{data.learners.map((l) => (
                        <tr key={l.user_id}><td>{l.name}</td><td>{l.readiness === null ? "—" : Math.round(l.readiness)}</td>
                          <td>{l.submitted} / {l.assigned}</td><td>{ago(l.last_active_at)}</td></tr>
                      ))}</tbody>
                    </table>
                  ) : <p className="ld-empty">{data.view === "students" ? "No students yet. They appear once they join with your join codes." : "No learners yet."}</p>}
                </article>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
