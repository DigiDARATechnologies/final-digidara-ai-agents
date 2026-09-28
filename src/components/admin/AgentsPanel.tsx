import { AGENTS } from "../../data/agents";
import { fetchAgents } from "../../lib/adminApi";
import { agentLabel, formatDate, formatNumber, timeAgo } from "./adminFormat";
import { useLoad } from "./useLoad";

export default function AgentsPanel() {
  const { data, error, loading, reload } = useLoad(fetchAgents, []);
  if (loading && !data) return <p className="admin-loading">Loading agents…</p>;
  if (error) return <div className="admin-error">{error} <button className="btn btn-outline btn-sm" onClick={reload}>Retry</button></div>;
  if (!data) return null;

  const usageFor = (agentName: string) => {
    const chatAgent = AGENTS.find((agent) => agent.backendAgentName === agentName);
    return chatAgent ? data.chat_usage.find((row) => row.agent_id === chatAgent.id) : undefined;
  };
  const registered = new Set(data.agents.map((agent) => agent.agent_name));
  const unbuilt = AGENTS.filter((agent) => !agent.backendAgentName || !registered.has(agent.backendAgentName));

  return (
    <div className="admin-section">
      <div className="admin-toolbar">
        <small className="admin-loading">{data.agents.filter((a) => a.online).length} of {data.agents.length} registered agent versions online</small>
        <button className="btn btn-outline btn-sm" onClick={reload} disabled={loading}>{loading ? "Refreshing…" : "Refresh"}</button>
      </div>
      <div className="admin-agent-grid">
        {data.agents.map((agent) => {
          const usage = usageFor(agent.agent_name);
          const chatAgent = AGENTS.find((candidate) => candidate.backendAgentName === agent.agent_name);
          return (
            <article className="admin-agent-card" key={`${agent.agent_name}@${agent.version}`}>
              <header>
                <span className="admin-agent-icon" style={{ background: chatAgent?.color }}>{chatAgent?.icon ?? "🤖"}</span>
                <div>
                  <strong>{chatAgent?.name ?? agent.agent_name}</strong>
                  <small>{agent.agent_name} · {agent.version}</small>
                </div>
                <span className={`admin-badge ${agent.online ? "badge-active" : "badge-rejected"}`}>{agent.online ? "online" : "offline"}</span>
              </header>
              <p>{agent.description}</p>
              <dl>
                <div><dt>Last heartbeat</dt><dd>{timeAgo(agent.heartbeat_age_seconds)}</dd></div>
                <div><dt>Plan tier</dt><dd>{agent.plan_tier}</dd></div>
                <div><dt>Owner</dt><dd>{agent.owner || "—"}</dd></div>
                <div><dt>Chats</dt><dd>{usage ? formatNumber(usage.chats) : "0"}</dd></div>
                <div><dt>Users</dt><dd>{usage ? formatNumber(usage.users) : "0"}</dd></div>
                <div><dt>Messages</dt><dd>{usage ? formatNumber(usage.messages) : "0"}</dd></div>
                <div><dt>Last chat</dt><dd>{formatDate(usage?.last_active)}</dd></div>
              </dl>
              <details>
                <summary>{agent.actions.length} action{agent.actions.length === 1 ? "" : "s"} and endpoint</summary>
                <code className="admin-endpoint">{agent.endpoint}</code>
                <div className="admin-chips">{agent.actions.map((action) => <span key={action}>{action}</span>)}</div>
              </details>
            </article>
          );
        })}
      </div>
      {unbuilt.length > 0 && (
        <>
          <h4>Listed in the store but not connected</h4>
          <div className="admin-chips">{unbuilt.map((agent) => <span key={agent.id}>{agentLabel(agent.id)}</span>)}</div>
        </>
      )}
    </div>
  );
}
