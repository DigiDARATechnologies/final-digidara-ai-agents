import { useEffect, useState } from "react";
import { ScoreRing } from "../ReadinessView";
import { BAND_TONE, type Band, type OrgMember } from "../../lib/learnerApi";
import { fetchFilteredMembers, type StaffLogin } from "../../lib/orgApi";

function bandFor(score: number | null): Band {
  if (score === null) return "not_started";
  return score >= 80 ? "job_ready" : score >= 60 ? "almost_ready" : score >= 40 ? "developing" : "not_ready";
}

function lastActive(iso: string | null | undefined): string {
  if (!iso) return "Never";
  return new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/** One staff member: their details and the students they look after, each with a job readiness score. */
export default function StaffStudents({ orgId, person, details, onOpen, onClose }: {
  orgId: string; person: StaffLogin; details: string; onOpen: (member: OrgMember) => void; onClose: () => void;
}) {
  const [students, setStudents] = useState<OrgMember[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setStudents(null);
    setError("");
    fetchFilteredMembers(orgId, { staff: person.user_id }).then(setStudents).catch((err) => setError((err as Error).message));
  }, [orgId, person.user_id]);

  const scores = (students ?? []).map((m) => m.readiness?.overall).filter((v): v is number => typeof v === "number");
  const average = scores.length ? Math.round((scores.reduce((a, b) => a + b, 0) / scores.length) * 10) / 10 : null;

  return (
    <section className="org-card org-staff-students" aria-label={`${person.name}'s students`}>
      <div className="org-card-head">
        <div className="org-staff-head">
          <span className="org-avatar" aria-hidden="true">{person.name.slice(0, 1).toUpperCase()}</span>
          <div>
            <h3>{person.name}</h3>
            <small className="rd-muted">{person.email}{person.has_signed_in ? "" : " · not signed in yet"}</small>
            {details && <span className="org-staff-class">{details}</span>}
          </div>
        </div>
        <button type="button" className="link-btn" onClick={onClose}>Close</button>
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      {students === null && !error ? <div className="org-skeleton" /> : students && (
        <>
          <div className="org-kpis">
            <div className="org-kpi org-kpi-ring">
              <ScoreRing score={average} band={bandFor(average)} size={72} />
              <span>Average job readiness</span>
            </div>
            <div className="org-kpi"><b>{students.length}</b><span>Students</span></div>
            <div className="org-kpi"><b>{students.filter((m) => m.has_signed_in).length}</b><span>Signed in</span></div>
            <div className="org-kpi"><b>{scores.filter((s) => s >= 80).length}</b><span>Job ready</span></div>
          </div>
          <div className="org-table-wrap">
            <table className="org-table">
              <thead><tr><th>Student</th><th>Class</th><th>Job readiness</th><th>Last active</th></tr></thead>
              <tbody>
                {students.map((m) => (
                  <tr key={m.member_id} className="org-row" tabIndex={0} onClick={() => onOpen(m)} onKeyDown={(e) => e.key === "Enter" && onOpen(m)}>
                    <td><div className="org-person"><span className="org-avatar" aria-hidden="true">{m.name.slice(0, 1).toUpperCase()}</span>
                      <span><b>{m.name}</b><small>{m.email}{m.external_id ? ` · ${m.external_id}` : ""}</small></span></div></td>
                    <td>{[m.department, m.year, m.section].filter(Boolean).join(" · ") || <span className="rd-muted">—</span>}</td>
                    <td>{!m.progress_shared ? <span className="rd-muted">{m.has_signed_in ? "Not shared" : "Not signed in"}</span>
                      : m.readiness ? <span className={`og-band tone-${BAND_TONE[m.readiness.band]}`}>
                        {m.readiness.overall === null ? "–" : Math.round(m.readiness.overall)} · {m.readiness.band_label}</span>
                      : <span className="rd-muted">Not checked</span>}</td>
                    <td>{lastActive(m.last_active_at)}</td>
                  </tr>
                ))}
                {students.length === 0 && (
                  <tr><td colSpan={4} className="org-empty">No students yet. Students are {person.name}'s when they are on
                    {" "}{person.name}'s student list or join with {person.name}'s join code.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
