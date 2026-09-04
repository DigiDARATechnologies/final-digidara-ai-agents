import { CATEGORIES, AGENTS } from "../data/agents";
import AgentCard from "./AgentCard";

interface StoreViewProps {
  activeTab: string;
  searchTerm: string;
  onTabChange: (tab: string) => void;
  onSearchChange: (term: string) => void;
  onOpenAgent: (agentId: string) => void;
}

export default function StoreView({ activeTab, searchTerm, onTabChange, onSearchChange, onOpenAgent }: StoreViewProps) {
  const term = searchTerm.trim().toLowerCase();
  const searching = term.length > 0;

  const tabOk = (agent: (typeof AGENTS)[number]) =>
    activeTab === "Top Picks" ? agent.category!.includes("Top Picks") : agent.category!.includes(activeTab);
  const inSearch = (agent: (typeof AGENTS)[number]) =>
    !term || agent.name.toLowerCase().includes(term) || agent.desc!.toLowerCase().includes(term);

  const list = AGENTS.filter((a) => tabOk(a) && inSearch(a));
  const showFeatured = !searching && activeTab === "Top Picks";
  const allTitle = searching ? `Results for "${searchTerm}"` : activeTab === "Top Picks" ? "All agents" : `${activeTab} agents`;

  return (
    <section className="view view-store active" id="view-store">
      <div className="store-hero">
        <h1>
          DigiDARA <span className="grad-text">Agents</span>
        </h1>
        <p>Discover and run specialized AI agents that combine instructions, live data and skills to get real work done.</p>

        <div className="search-bar glow-border">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
            <path d="M21 21l-4.3-4.3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <input
            type="text"
            placeholder="Search agents…"
            value={searchTerm}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </div>

        <div className="tabs">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              className={`tab-btn${cat === activeTab ? " active" : ""}`}
              onClick={() => onTabChange(cat)}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      <div className="store-body">
        {showFeatured && (
          <section className="section" id="featuredSection">
            <h2>
              Featured <span className="muted">Curated top picks from this week</span>
            </h2>
            <div className="grid grid-featured">
              {AGENTS.filter((a) => a.featured).map((a) => (
                <AgentCard key={a.id} agent={a} onClick={onOpenAgent} />
              ))}
            </div>
          </section>
        )}

        <section className="section">
          <h2>{allTitle}</h2>
          <div className="grid grid-agents">
            {list.map((a) => (
              <AgentCard key={a.id} agent={a} onClick={onOpenAgent} />
            ))}
          </div>
          {list.length === 0 && (
            <p className="empty-state">No agents match your search. Try a different keyword or category.</p>
          )}
        </section>
      </div>
    </section>
  );
}
