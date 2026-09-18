import type { CapstoneFlowState, CapstoneStep } from "../lib/capstoneFlow";
import type { User } from "../types";

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
        <div><span>Capstone agent</span><h2>Project dashboard</h2></div>
        <button className="icon-btn" onClick={onClose} aria-label="Close dashboard">x</button>
      </div>

      <div className="dashboard-status-card">
        <div className="dashboard-status-row"><strong>{STEP_LABELS[state.step]}</strong><span>{STEP_PROGRESS[state.step]}%</span></div>
        <div className="progress-track"><span style={{ width: `${STEP_PROGRESS[state.step]}%` }} /></div>
        <p>The agent is monitoring this workflow and will keep all verification, choices, uploads, and feedback in the same chat.</p>
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
          <div><dt>Requested topic</dt><dd>{state.topicSeed ?? "Not set"}</dd></div>
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
      {state.scoreReasoning && (
        <div className="dashboard-section">
          <h3>How the score was decided</h3>
          <p className="muted">{state.scoreReasoning}</p>
        </div>
      )}
      {state.codeQualityScore && (
        <div className="dashboard-section">
          <h3>Code review breakdown</h3>
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
      {state.revisionNotes && <div className="dashboard-alert"><strong>Revision requested</strong><p>{state.revisionNotes}</p></div>}
    </aside>
  );
}
