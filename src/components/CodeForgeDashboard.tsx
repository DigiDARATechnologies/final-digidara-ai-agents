import type { CodeForgeFlowState, CodeForgeStep } from "../lib/codeforgeFlow";
import type { User } from "../types";

interface CodeForgeDashboardProps {
  user: User;
  state: CodeForgeFlowState;
  onClose: () => void;
}

const STEP_LABELS: Record<CodeForgeStep, string> = {
  awaiting_course: "Choose a course",
  awaiting_technology: "Choose a technology",
  awaiting_topic: "Choose a topic",
  awaiting_problem: "Choose a problem",
  awaiting_code: "Solving a problem",
  awaiting_mcq_answer: "Answering a question",
};

const STEP_PROGRESS: Record<CodeForgeStep, number> = {
  awaiting_course: 10,
  awaiting_technology: 30,
  awaiting_topic: 50,
  awaiting_problem: 70,
  awaiting_code: 90,
  awaiting_mcq_answer: 90,
};

export default function CodeForgeDashboard({ user, state, onClose }: CodeForgeDashboardProps) {
  const result = state.lastResult;

  return (
    <aside className="agent-dashboard">
      <div className="dashboard-head">
        <div><span>CodeForge Agent</span><h2>Practice Dashboard</h2></div>
        <button className="icon-btn" onClick={onClose} aria-label="Close dashboard">x</button>
      </div>

      <div className="dashboard-status-card">
        <div className="dashboard-status-row"><strong>{STEP_LABELS[state.step]}</strong><span>{STEP_PROGRESS[state.step]}%</span></div>
        <div className="progress-track"><span style={{ width: `${STEP_PROGRESS[state.step]}%` }} /></div>
        <p>The agent tracks your course path and latest run/submit result here while you code in chat.</p>
      </div>

      <div className="dashboard-section">
        <h3>Candidate</h3>
        <dl>
          <div><dt>Name</dt><dd>{state.studentName ?? user.name}</dd></div>
          <div><dt>Email</dt><dd>{user.email}</dd></div>
        </dl>
      </div>

      <div className="dashboard-section">
        <h3>Path</h3>
        <dl>
          <div><dt>Course</dt><dd>{state.courseName ?? "Not selected"}</dd></div>
          <div><dt>Technology</dt><dd>{state.technologyName ?? "Not selected"}</dd></div>
          <div><dt>Topic</dt><dd>{state.topicName ?? "Not selected"}</dd></div>
          <div><dt>Problem</dt><dd>{state.problemName ?? "Not selected"}</dd></div>
        </dl>
      </div>

      {result && (
        <div className={`dashboard-result ${result.status === "Accepted" ? "pass" : "fail"}`}>
          <span>{result.mode === "submit" ? "Submit result" : "Run result"}</span>
          <strong>{result.passedTests}/{result.totalTests} tests</strong>
          {result.mode === "submit" && <p>Score: {result.score}/100</p>}
          <p>{result.status}</p>
        </div>
      )}
      {state.lastGuidance && (
        <div className="dashboard-alert">
          <strong>{state.lastGuidance.source === "ai" ? "AI Tutor" : "Guided fallback"}</strong>
          <p>{state.lastGuidance.explanation}</p>
        </div>
      )}
    </aside>
  );
}
