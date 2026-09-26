import { useState } from "react";
import { confirmCertificate, downloadCertificate, downloadFinalReport, previewCertificate, type CertificatePreview } from "../lib/capstoneApi";
import { CAPSTONE_EXAMPLE_FILES } from "../lib/capstoneExamples";
import type { CapstoneFlowState, CapstoneStep } from "../lib/capstoneFlow";
import type { User } from "../types";

/** Shown only once BOTH the code score and the viva are passed -- the backend
 * refuses to issue the report before that, so this never offers a dead button. */
function FinalReportButton({ submissionId }: { submissionId: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function download() {
    setBusy(true);
    setError("");
    try {
      await downloadFinalReport(submissionId);
    } catch (caught) {
      setError((caught as Error).message || "The final report is unavailable.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="dashboard-section">
      <h3>Final Report</h3>
      <p className="muted">Your score, viva results and project details, as a PDF.</p>
      <button type="button" className="btn btn-primary" disabled={busy} onClick={download}>
        {busy ? "Preparing report..." : "Download final report (PDF)"}
      </button>
      {error && <p className="form-error" role="alert">{error}</p>}
    </div>
  );
}

/** The certificate: preview it, correct the name if needed (the only editable thing),
 * click OK to issue it, then download the PDF. Shown only once BOTH the code score and
 * the viva are passed -- the backend refuses earlier. What the student approves is what
 * they get: OK is offered only for the name they have actually previewed. */
function CertificateSection({ submissionId }: { submissionId: string }) {
  const [preview, setPreview] = useState<CertificatePreview | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState<"" | "preview" | "confirm" | "download">("");
  const [error, setError] = useState("");

  async function run<T>(kind: "preview" | "confirm" | "download", work: () => Promise<T>): Promise<T | undefined> {
    setBusy(kind);
    setError("");
    try {
      return await work();
    } catch (caught) {
      setError((caught as Error).message || "The certificate is unavailable.");
      return undefined;
    } finally {
      setBusy("");
    }
  }

  async function load(requestedName?: string) {
    const shown = await run("preview", () => previewCertificate(submissionId, requestedName));
    if (shown) {
      setPreview(shown);
      setName(shown.name);
    }
  }

  async function confirm() {
    const done = await run("confirm", () => confirmCertificate(submissionId, name.trim()));
    if (done) await load();   // show the issued certificate, name locked
  }

  const confirmed = !!preview?.confirmed;
  const previewedName = preview?.name ?? "";
  const nameChanged = name.trim() !== previewedName;

  return (
    <div className="dashboard-section certificate-section">
      <h3>Your Certificate</h3>
      {!preview && (
        <>
          <p className="muted">You passed the project and the viva. Preview your certificate, check your name, then click OK to issue it.</p>
          <button type="button" className="btn btn-primary" disabled={busy !== ""} onClick={() => load()}>
            {busy === "preview" ? "Preparing preview..." : "Preview my certificate"}
          </button>
        </>
      )}
      {preview && (
        <>
          <img className="certificate-preview" alt={`Certificate for ${preview.name}: ${preview.project_title}`} src={`data:${preview.content_type};base64,${preview.preview}`} />
          {confirmed ? (
            <>
              <p className="muted">Your certificate is issued (ID {preview.certificate_id}). The name can no longer be changed.</p>
              <button type="button" className="btn btn-primary" disabled={busy !== ""} onClick={() => run("download", () => downloadCertificate(submissionId))}>
                {busy === "download" ? "Preparing PDF..." : "Download certificate (PDF)"}
              </button>
            </>
          ) : (
            <>
              <label className="field">
                Name on the Certificate
                <input value={name} maxLength={60} onChange={(event) => setName(event.target.value)} aria-label="Name on the certificate" />
              </label>
              <p className="muted">Only the name can be edited. Update the preview to see a change, then click OK to issue the certificate.</p>
              <div className="certificate-actions">
                <button type="button" className="btn" disabled={busy !== "" || !name.trim() || !nameChanged} onClick={() => load(name.trim())}>
                  {busy === "preview" ? "Updating..." : "Update preview"}
                </button>
                <button type="button" className="btn btn-primary" disabled={busy !== "" || !name.trim() || nameChanged} onClick={confirm}>
                  {busy === "confirm" ? "Issuing..." : "OK"}
                </button>
              </div>
            </>
          )}
        </>
      )}
      {error && <p className="form-error" role="alert">{error}</p>}
    </div>
  );
}

interface AgentDashboardProps {
  user: User;
  state: CapstoneFlowState;
  onClose: () => void;
}

const STEP_LABELS: Record<CapstoneStep, string> = {
  awaiting_topic_request: "Choose a topic",
  awaiting_topic_choice: "Choose project",
  awaiting_timer_confirm: "Ready to start",
  awaiting_submission: "Project in progress",
  awaiting_viva_answer: "Viva in progress",
  graded: "Graded",
};

const STEP_PROGRESS: Record<CapstoneStep, number> = {
  awaiting_topic_request: 15,
  awaiting_topic_choice: 45,
  awaiting_timer_confirm: 60,
  awaiting_submission: 78,
  awaiting_viva_answer: 92,
  graded: 100,
};

export default function AgentDashboard({ user, state, onClose }: AgentDashboardProps) {
  return (
    <aside className="agent-dashboard">
      <div className="dashboard-head">
        <div><span>Capstone Agent</span><h2>Project Dashboard</h2></div>
        <button className="icon-btn" onClick={onClose} aria-label="Close dashboard">x</button>
      </div>

      <div className="dashboard-status-card">
        <div className="dashboard-status-row"><strong>{STEP_LABELS[state.step]}</strong><span>{STEP_PROGRESS[state.step]}%</span></div>
        <div className="progress-track"><span style={{ width: `${STEP_PROGRESS[state.step]}%` }} /></div>
        <p>The agent is monitoring this workflow and will keep all verification, choices, uploads, and feedback in the same chat.</p>
      </div>

      <div className="dashboard-section">
        <h3>Example Files</h3>
        <p className="muted">See the expected report format and zip folder structure. They are the same for every project; write your own for yours.</p>
        <div className="chat-options">
          {CAPSTONE_EXAMPLE_FILES.map((file) => (
            <a key={file.href} className="chat-option-link" href={file.href} download={file.download}>
              <strong>{file.label}</strong>
              <span>{file.description}</span>
            </a>
          ))}
        </div>
      </div>

      <div className="dashboard-section">
        <h3>Learner</h3>
        <dl>
          <div><dt>Name</dt><dd>{user.name}</dd></div>
          <div><dt>Email</dt><dd>{user.email}</dd></div>
          <div><dt>Mobile</dt><dd>{user.mobile}</dd></div>
        </dl>
      </div>

      <div className="dashboard-section">
        <h3>Project</h3>
        <dl>
          <div><dt>Requested Topic</dt><dd>{state.topicSeed ?? "Not set"}</dd></div>
          <div><dt>Topic</dt><dd>{state.chosenTopic?.title ?? "Not selected"}</dd></div>
          <div><dt>Deadline</dt><dd>{state.deadlineAt ? new Date(state.deadlineAt).toLocaleString() : "Not started"}</dd></div>
          <div><dt>Files</dt><dd>{state.docxFile || state.zipFile ? `${state.docxFile ? "Report " : ""}${state.zipFile ? "Source" : ""}` : "Not uploaded"}</dd></div>
        </dl>
      </div>

      {state.finalScore != null && (
        <div className={`dashboard-result ${state.passed ? "pass" : "fail"}`}>
          <span>{state.passed ? "Passed" : "Needs improvement"}</span>
          <strong>{state.finalScore}/100</strong>
          {state.feedback && <p>{state.feedback}</p>}
        </div>
      )}
      {state.step === "graded" && state.passed && state.vivaSubmissionId && <CertificateSection submissionId={state.vivaSubmissionId} />}
      {state.step === "graded" && state.passed && state.vivaSubmissionId && <FinalReportButton submissionId={state.vivaSubmissionId} />}
      {state.scoreReasoning && (
        <div className="dashboard-section">
          <h3>How the score was decided</h3>
          <p className="muted">{state.scoreReasoning}</p>
        </div>
      )}
      {state.codeQualityScore && (
        <div className="dashboard-section">
          <h3>Code Review Breakdown</h3>
          <dl>
            <div><dt>Structure</dt><dd>{state.codeQualityScore.structure_score ?? "-"}/25</dd></div>
            <div><dt>Syntax</dt><dd>{state.codeQualityScore.syntax_score ?? "-"}/25</dd></div>
            <div><dt>Maintainability</dt><dd>{state.codeQualityScore.maintainability_score ?? "-"}/25</dd></div>
            <div><dt>Completeness</dt><dd>{state.codeQualityScore.completeness_score ?? "-"}/25</dd></div>
          </dl>
          {!!state.codeQualityScore.strengths?.length && (
            <>
              <p className="muted">Strengths</p>
              <ul className="dashboard-list">
                {state.codeQualityScore.strengths.map((item, i) => <li key={i}>{item}</li>)}
              </ul>
            </>
          )}
          {!!state.codeQualityScore.weaknesses?.length && (
            <>
              <p className="muted">Weaknesses</p>
              <ul className="dashboard-list">
                {state.codeQualityScore.weaknesses.map((item, i) => <li key={i}>{item}</li>)}
              </ul>
            </>
          )}
        </div>
      )}
      {state.revisionNotes && <div className="dashboard-alert"><strong>Revision Requested</strong><p>{state.revisionNotes}</p></div>}
    </aside>
  );
}
