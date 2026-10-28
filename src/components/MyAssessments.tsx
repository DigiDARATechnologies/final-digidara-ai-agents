import { useEffect, useState } from "react";
import { fetchMyAssessments, type MyAssessment, type MyAssessments as Data } from "../lib/proctorApi";
import "./LearningDashboard.css";

const STATUS: Record<MyAssessment["status"], string> = {
  open: "Open now", in_progress: "In progress", upcoming: "Upcoming", submitted: "Submitted", missed: "Missed",
};

function when(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : "";
}

function describe(a: MyAssessment): string {
  const c = a.config || {};
  if (a.kind === "knowledge_test") return `Knowledge test${c.num_questions ? ` · ${c.num_questions} questions` : ""}`;
  const round = c.round_type === "hr" ? "HR interview" : `Technical interview${c.role_name ? ` · ${c.role_name}` : c.subject ? ` · ${c.subject}` : ""}`;
  return `${round}${c.num_questions ? ` · ${c.num_questions} questions` : ""}${c.level_label ? ` · ${c.level_label}` : ""}`;
}

/** The learner's assessments: what their organization (or their staff member)
 * gave them. Only visible once they have joined the organization. */
export default function MyAssessments({ onOpen, onBack, onJoin }: {
  onOpen: (token: string) => void; onBack?: () => void; onJoin?: () => void;
}) {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { fetchMyAssessments().then(setData).catch((err) => setError((err as Error).message)); }, []);
  const order: MyAssessment["status"][] = ["in_progress", "open", "upcoming", "submitted", "missed"];
  const sorted = [...(data?.assessments ?? [])].sort((a, b) => order.indexOf(a.status) - order.indexOf(b.status));
  return (
    <div className="pv-page ld-page">
      <div className="pv-inner ld-inner">
        {onBack && <button className="hp-back" onClick={onBack}>← Back</button>}
        <header className="ld-head">
          <div>
            <span className="ld-kicker">{data?.organization || "Your organization"}</span>
            <h1>Assessments</h1>
            <p>Tests and mock interviews your trainers have set for you. Taking them is free.</p>
          </div>
        </header>
        {error && <p className="form-error" role="alert">{error}</p>}
        {!data && !error && <div className="ld-skeleton" />}
        {data && !data.member && (
          <div className="ld-card">
            <h2>Join your organization first</h2>
            <p className="ld-empty">Assessments appear here once you join your college or company with the join code your trainer gave you.</p>
            {onJoin && <button type="button" className="btn btn-primary btn-sm" onClick={onJoin}>Join with a code</button>}
          </div>
        )}
        {data?.member && sorted.length === 0 && <p className="ld-empty">No assessments for you yet. Your trainers' assessments will appear here.</p>}
        {data?.member && sorted.length > 0 && (
          <div className="ma-list">
            {sorted.map((a) => {
              const canOpen = a.status === "open" || a.status === "in_progress";
              const token = a.path.split("/").pop() ?? "";
              return (
                <article key={a.id} className={`ld-card ma-item st-${a.status}`}>
                  <div className="ma-main">
                    <span className={`ld-pill st-${a.status}`}>{STATUS[a.status]}</span>
                    <h2>{a.title}</h2>
                    <p>{describe(a)}{a.by ? ` · by ${a.by}` : ""}</p>
                    <small>
                      {a.status === "upcoming" && a.opens_at ? `Opens ${when(a.opens_at)}` : ""}
                      {canOpen && a.closes_at ? `Closes ${when(a.closes_at)}` : ""}
                      {a.status === "missed" && a.closes_at ? `Closed ${when(a.closes_at)}` : ""}
                    </small>
                  </div>
                  <div className="ma-side">
                    {a.status === "submitted" && <strong>{a.percent === null ? "Done" : `${Math.round(a.percent)}%`}</strong>}
                    {canOpen && <button type="button" className="btn btn-primary btn-sm" onClick={() => onOpen(token)}>
                      {a.status === "in_progress" ? "Continue" : "Start"}</button>}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
