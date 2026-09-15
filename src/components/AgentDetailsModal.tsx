import type { Agent } from "../types";

interface AgentDetailsModalProps {
  agent: Agent | null;
  onClose: () => void;
  onStartChat: (agentId: string) => void;
}

const STARTERS: Record<string, string[]> = {
  "career-guide": ["Help me choose a career path", "Create a 2-year career roadmap", "What skills should I learn next?", "Review my career goals"],
  "resume-builder": ["Build my resume from scratch", "Tailor my resume for a job", "Check my resume for ATS", "Improve my professional summary"],
  "mock-interview": ["Start a technical interview", "Practice an HR interview", "Run a behavioral interview", "Help me prepare for my next round"],
  leetcode: ["Give me an easy DSA problem", "Practice arrays and strings", "Start a timed coding challenge", "Help me understand dynamic programming"],
  "capstone-project": ["Check my project eligibility", "Help me choose a project topic", "Start my capstone project", "Explain the submission process"],
};

function startersFor(agent: Agent) {
  return STARTERS[agent.id] ?? [
    `Help me get started with ${agent.name}`,
    `What can ${agent.name} do for me?`,
    agent.greeting,
    `Create a step-by-step plan with ${agent.name}`,
  ];
}

export default function AgentDetailsModal({ agent, onClose, onStartChat }: AgentDetailsModalProps) {
  if (!agent) return null;
  const category = agent.category?.find((item) => item !== "Top Picks") ?? "Productivity";
  const starters = startersFor(agent);
  const conversations = `${Math.max(12, agent.id.length * 7)}K+`;

  return (
    <div className="agent-detail-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="agent-detail-modal" role="dialog" aria-modal="true" aria-labelledby="agent-detail-title">
        <button className="agent-detail-close" onClick={onClose} aria-label="Close agent details">×</button>

        <div className="agent-detail-scroll">
          <header className="agent-detail-hero">
            <span className="agent-detail-icon" style={{ background: `linear-gradient(145deg, ${agent.color}, #365f91)` }}>{agent.icon}</span>
            <h2 id="agent-detail-title">{agent.name}</h2>
            <p className="agent-detail-author">By {agent.author ?? "DigiDARA"}</p>
            <p className="agent-detail-description">{agent.desc}</p>

            <div className="agent-detail-stats">
              <div><strong>★ {agent.rating ?? 4.8}</strong><span>Agent rating</span></div>
              <div><strong>#{Math.max(1, agent.id.length - 2)}</strong><span>in {category}</span></div>
              <div><strong>{conversations}</strong><span>Conversations</span></div>
            </div>
          </header>

          <section className="agent-detail-section">
            <h3>Conversation starters</h3>
            <div className="starter-grid">
              {starters.map((starter) => <button key={starter} onClick={() => onStartChat(agent.id)}>{starter}</button>)}
            </div>
          </section>

          <section className="agent-detail-section">
            <h3>Capabilities</h3>
            <div className="capability-list">
              <div><span>✓</span><p><strong>Specialized guidance</strong><small>Understands your request and guides you through a focused workflow.</small></p></div>
              <div><span>✓</span><p><strong>Personalized responses</strong><small>Adapts recommendations and output to the details you provide.</small></p></div>
              {agent.kind && <div><span>✓</span><p><strong>Connected agent workflow</strong><small>Runs the dedicated {agent.name} experience from start to finish.</small></p></div>}
            </div>
          </section>

          <section className="agent-detail-section agent-about">
            <h3>About</h3>
            <p>{agent.desc} Start a conversation and the agent will guide you through the next steps.</p>
            <div className="agent-tags">{agent.category?.map((item) => <span key={item}>{item}</span>)}</div>
          </section>
        </div>

        <footer className="agent-detail-footer">
          <button onClick={() => onStartChat(agent.id)}><span>◯</span> Start chat</button>
        </footer>
      </section>
    </div>
  );
}
