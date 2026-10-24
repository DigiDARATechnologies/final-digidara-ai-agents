import { useEffect, useState } from "react";
import { fetchProctorDetail, fetchSnapshotUrl, type ProctorDetail, type ProctorSummary } from "../../lib/proctorApi";
import { EVENT_LABELS, formatWhen as when, integrityBand, resultText } from "../../lib/proctoring";
import { downloadKnowledgeReport, fetchAdminKnowledgeReport, type KnowledgeReport } from "../../lib/knowledgeApi";
import KnowledgeReportView from "../KnowledgeReportView";
import "../Proctor.css";

const AGENT_TEXT: Record<string, string> = { mock_interview_agent: "Mock interview", capstone_project_agent: "Capstone viva", knowledge_test_agent: "Knowledge test" };
const STATUS_TEXT: Record<string, string> = { active: "In progress", completed: "Finished", terminated: "Ended: too many warnings" };

export function Integrity({ score }: { score: number }) {
  return <span className={`integrity integrity-${integrityBand(score)}`} title="Integrity score out of 100">{score}</span>;
}

/** Proctored sittings as a table; "View" opens the report. */
export function ProctorTable({ rows, showPerson, onOpen }: { rows: ProctorSummary[]; showPerson: boolean; onOpen: (id: string) => void }) {
  if (!rows.length) return <p className="org-empty">No proctored tests yet.</p>;
  return (
    <div className="assess-table-wrap">
      <table className="assess-table">
        <thead>
          <tr>
            {showPerson ? <th>Learner</th> : <th>Test</th>}
            <th>Status</th><th>Result</th><th>Integrity</th><th>Warnings</th><th>Started</th><th />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.session_id}>
              <td>{showPerson ? <><b>{row.name || "-"}</b><br /><span className="assess-sub">{row.email}</span></> : AGENT_TEXT[row.agent_name] ?? row.agent_name}</td>
              <td>{STATUS_TEXT[row.status] ?? row.status}</td>
              <td>{resultText(row.result)}</td>
              <td><Integrity score={row.integrity} /></td>
              <td>{row.warnings}</td>
              <td>{when(row.started_at)}</td>
              <td><button type="button" className="link-btn" onClick={() => onOpen(row.session_id)}>View</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Snapshot({ orgId, sessionId, shot }: { orgId: string; sessionId: string; shot: ProctorDetail["snapshots"][number] }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    let alive = true;
    let made = "";
    fetchSnapshotUrl(orgId, sessionId, shot.id).then((next) => {
      made = next;
      if (alive) setUrl(next); else URL.revokeObjectURL(next);
    }).catch(() => {});
    return () => { alive = false; if (made) URL.revokeObjectURL(made); };
  }, [orgId, sessionId, shot.id]);
  const faces = shot.faces == null ? "" : shot.faces === 1 ? "1 face" : `${shot.faces} faces`;
  return (
    <figure>
      {url ? <img src={url} alt={`Camera photo at ${when(shot.at)}`} /> : <div className="org-skeleton" style={{ height: 82 }} />}
      <figcaption>{new Date(shot.at ?? "").toLocaleTimeString()}{faces ? ` · ${faces}` : ""}</figcaption>
    </figure>
  );
}

/** One proctored sitting: result, integrity, the warnings timeline and the camera photos. */
export function ProctorReport({ orgId, sessionId, onClose }: { orgId: string; sessionId: string; onClose: () => void }) {
  const [detail, setDetail] = useState<ProctorDetail | null>(null);
  const [error, setError] = useState("");
  const [answers, setAnswers] = useState<KnowledgeReport | null>(null);
  const [answersNote, setAnswersNote] = useState("");
  useEffect(() => {
    fetchProctorDetail(orgId, sessionId).then((next) => {
      setDetail(next);
      if (next.agent_name === "knowledge_test_agent") {
        fetchAdminKnowledgeReport(orgId, sessionId).then(setAnswers).catch((err) => setAnswersNote((err as Error).message));
      }
    }).catch((err) => setError((err as Error).message));
  }, [orgId, sessionId]);

  return (
    <div className="assess-backdrop" role="dialog" aria-modal="true" aria-labelledby="proctor-report-title" onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div className="assess-card">
        <div className="assess-item-head">
          <h2 id="proctor-report-title">Proctoring report</h2>
          <button type="button" className="org-icon-btn" aria-label="Close" onClick={onClose}>×</button>
        </div>
        {error && <p className="proctor-error" role="alert">{error}</p>}
        {!detail && !error && <div className="org-skeleton" />}
        {detail && (
          <>
            <p className="assess-org">{detail.name} · {detail.email} · {AGENT_TEXT[detail.agent_name] ?? detail.agent_name}</p>
            <div className="assess-facts">
              <div className="assess-fact"><span>Status</span><strong>{STATUS_TEXT[detail.status] ?? detail.status}</strong></div>
              <div className="assess-fact"><span>Result</span><strong>{resultText(detail.result)}</strong></div>
              <div className="assess-fact"><span>Integrity</span><strong><Integrity score={detail.integrity} /> / 100</strong></div>
              <div className="assess-fact"><span>Warnings</span><strong>{detail.warnings} of {detail.settings.max_warnings}</strong></div>
              <div className="assess-fact"><span>Started</span><strong>{when(detail.started_at)}</strong></div>
            </div>
            {detail.agent_name === "knowledge_test_agent" && (
              answers
                ? <div style={{ margin: "0 0 16px" }}><KnowledgeReportView report={answers} onDownload={() => downloadKnowledgeReport({ orgId, sessionId }, `${answers.title}_${answers.learner}`)} /></div>
                : <p className="assess-sub">{answersNote || "Loading the answers…"}</p>
            )}
            <h3 style={{ margin: "0 0 4px", fontSize: 15 }}>What happened</h3>
            {detail.events.length === 0
              ? <p className="assess-sub">Nothing was flagged.</p>
              : (
                <ul className="proctor-timeline">
                  {detail.events.map((event, index) => (
                    <li key={`${event.at}-${index}`}>
                      <span><b>{EVENT_LABELS[event.kind] ?? event.kind}</b>{event.detail ? ` · ${event.detail}` : ""}</span>
                      <span className="assess-sub">{event.at ? new Date(event.at).toLocaleTimeString() : ""} · −{event.penalty}</span>
                    </li>
                  ))}
                </ul>
              )}
            {detail.settings.webcam && (
              <>
                <h3 style={{ margin: "16px 0 4px", fontSize: 15 }}>Camera photos</h3>
                <p className="assess-sub">Deleted {detail.retention_days} days after they were taken. Opening this report is recorded in the access log.</p>
                {detail.snapshots.length === 0
                  ? <p className="assess-sub">No photos (deleted, or none were taken).</p>
                  : <div className="proctor-shots">{detail.snapshots.map((shot) => <Snapshot key={shot.id} orgId={orgId} sessionId={detail.session_id} shot={shot} />)}</div>}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
