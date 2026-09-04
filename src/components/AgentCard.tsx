import type { Agent } from "../types";

interface AgentCardProps {
  agent: Agent;
  onClick: (agentId: string) => void;
}

export default function AgentCard({ agent, onClick }: AgentCardProps) {
  return (
    <article
      className="card"
      style={{ animationDelay: `${Math.random() * 0.15}s` }}
      onClick={() => onClick(agent.id)}
    >
      <span className="card-icon" style={{ background: agent.color }}>
        {agent.icon}
      </span>
      <div className="card-body">
        <h3>{agent.name}</h3>
        <p>{agent.desc}</p>
        <div className="card-foot">
          <span className="rating">★ {agent.rating}</span>
          <span>·</span>
          <span>By {agent.author}</span>
        </div>
      </div>
    </article>
  );
}
