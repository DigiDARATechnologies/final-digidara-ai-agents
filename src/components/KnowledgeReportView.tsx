import { useState } from "react";
import type { KnowledgeReport } from "../lib/knowledgeApi";
import "./Knowledge.css";

const LETTERS = ["A", "B", "C", "D"];
const VERDICT_TEXT: Record<string, string> = { correct: "Correct", partial: "Partly correct", wrong: "Incorrect", ungraded: "Not graded" };

/** The result of a knowledge test: shown to the learner, and to their organization's admins. */
export default function KnowledgeReportView({ report, onDownload, onClose }: { report: KnowledgeReport; onDownload: () => Promise<void>; onClose?: () => void }) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");
  const percent = Math.round(report.percent);
  const band = percent >= 75 ? "good" : percent >= 50 ? "fair" : "poor";
  return (
    <section className="kt-report" aria-label="Test report">
      <div className="kt-report-head">
        <div className={`kt-ring kt-ring-${band}`} style={{ ["--kt-p" as string]: `${percent}` }} aria-label={`${percent} percent`}>
          <strong>{percent}%</strong>
        </div>
        <div>
          <span className="proctor-badge">Report</span>
          <h2>{report.title}</h2>
          <p className="assess-sub">{[report.organization, report.learner].filter(Boolean).join(" · ")}</p>
          <div className="kt-stats">
            <span><b>{report.score}</b> / {report.max} points</span>
            <span><b>{report.rows.filter((r) => r.verdict === "correct").length}</b> correct</span>
            {report.integrity != null && <span>Integrity <b>{report.integrity}</b>/100</span>}
          </div>
        </div>
      </div>
      {report.summary && <p className="kt-summary">{report.summary}</p>}
      {(report.strengths.length > 0 || report.improve.length > 0) && (
        <div className="kt-two">
          {report.strengths.length > 0 && <div><h3>Strengths</h3><ul>{report.strengths.map((s) => <li key={s}>{s}</li>)}</ul></div>}
          {report.improve.length > 0 && <div><h3>To revise</h3><ul>{report.improve.map((s) => <li key={s}>{s}</li>)}</ul></div>}
        </div>
      )}
      <h3 className="kt-section">Question by question</h3>
      <ol className="kt-rows">
        {report.rows.map((row) => (
          <li key={row.number} className={`kt-row kt-${row.verdict}`}>
            <div className="kt-row-head">
              <b>Q{row.number}. {row.question}</b>
              <span className={`kt-verdict kt-verdict-${row.verdict}`}>{VERDICT_TEXT[row.verdict] ?? row.verdict} · {row.points} pt</span>
            </div>
            {row.qtype === "mcq" ? (
              <ul className="kt-row-options">
                {row.options.map((option, i) => {
                  const isRight = option === row.correct_answer;
                  const isYours = option === row.your_answer;
                  return <li key={i} className={`${isRight ? "right" : ""}${isYours && !isRight ? " yours" : ""}`}>
                    {LETTERS[i]}. {option}{isRight ? " ✓" : ""}{isYours ? " (your answer)" : ""}
                  </li>;
                })}
                {!row.your_answer && <li className="yours">{row.timed_out ? "No answer - time ran out" : "No answer"}</li>}
              </ul>
            ) : (
              <div className="kt-row-qa">
                <p><span>Your answer</span>{row.your_answer || (row.timed_out ? "No answer - time ran out" : "No answer")}</p>
                <p><span>Model answer</span>{row.correct_answer}</p>
              </div>
            )}
            {row.feedback && <p className="kt-feedback">{row.feedback}</p>}
          </li>
        ))}
      </ol>
      {error && <p className="proctor-error" role="alert">{error}</p>}
      <div className="assess-actions">
        <button type="button" className="btn btn-outline" disabled={downloading} onClick={async () => {
          setDownloading(true);
          setError("");
          try { await onDownload(); } catch (failure) { setError(failure instanceof Error ? failure.message : "The PDF could not be made."); } finally { setDownloading(false); }
        }}>{downloading ? "Preparing PDF…" : "Download PDF report"}</button>
        {onClose && <button type="button" className="btn btn-primary" onClick={onClose}>Close</button>}
      </div>
    </section>
  );
}
