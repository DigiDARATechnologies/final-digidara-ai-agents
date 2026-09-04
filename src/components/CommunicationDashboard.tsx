import type { CommunicationFlowState } from "../lib/communicationFlow";
import type { User } from "../types";

interface CommunicationDashboardProps {
  user: User;
  state: CommunicationFlowState;
  onClose: () => void;
}

const MODULE_LABELS: Record<string, string> = {
  writing: "Writing practice",
  speaking: "Speaking practice",
  pronunciation: "Pronunciation practice",
};

export default function CommunicationDashboard({ user, state, onClose }: CommunicationDashboardProps) {
  const progress =
    state.totalTurns && state.totalTurns > 0 && state.turnNumber
      ? Math.min(100, Math.round((state.turnNumber / state.totalTurns) * 100))
      : state.activeModule
        ? 30
        : 0;

  return (
    <aside className="agent-dashboard">
      <div className="dashboard-head">
        <div><span>Communication Coach</span><h2>Practice dashboard</h2></div>
        <button className="icon-btn" onClick={onClose} aria-label="Close dashboard">x</button>
      </div>

      <div className="dashboard-status-card">
        <div className="dashboard-status-row">
          <strong>{state.activeModule ? MODULE_LABELS[state.activeModule] : "Main menu"}</strong>
          <span>{progress}%</span>
        </div>
        <div className="progress-track"><span style={{ width: `${progress}%` }} /></div>
        <p>Pronunciation, Speaking and Writing are each scored live by the AI coach as you go.</p>
      </div>

      <div className="dashboard-section">
        <h3>Learner</h3>
        <dl>
          <div><dt>Name</dt><dd>{state.userName ?? user.name}</dd></div>
          <div><dt>Email</dt><dd>{user.email}</dd></div>
          <div><dt>Difficulty</dt><dd>{state.difficulty}</dd></div>
        </dl>
      </div>

      {state.activeModule && (
        <div className="dashboard-section">
          <h3>Session</h3>
          <dl>
            <div><dt>Turn</dt><dd>{state.turnNumber ?? "—"}{state.totalTurns ? ` / ${state.totalTurns}` : ""}</dd></div>
            {state.currentItemText && <div><dt>Practicing</dt><dd>{state.currentItemText}</dd></div>}
          </dl>
        </div>
      )}

      {state.lastScores && (
        <div className="dashboard-result pass">
          <span>Last turn scores</span>
          <dl>
            {Object.entries(state.lastScores).map(([key, value]) => (
              <div key={key}><dt>{key}</dt><dd>{value ?? "—"}/10</dd></div>
            ))}
          </dl>
        </div>
      )}
      {state.lastFeedback && (
        <div className="dashboard-alert">
          <strong>Coach feedback</strong>
          <p>{state.lastFeedback}</p>
        </div>
      )}
    </aside>
  );
}
