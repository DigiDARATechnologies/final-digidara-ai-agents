import { LIVE_AGENTS } from "../data/agents";
import AgentCard from "./AgentCard";

interface StoreViewProps {
  activeTab: string;
  searchTerm: string;
  onTabChange: (tab: string) => void;
  onSearchChange: (term: string) => void;
  onOpenAgent: (agentId: string) => void;
}

export default function StoreView({ activeTab, searchTerm, onTabChange, onSearchChange, onOpenAgent }: StoreViewProps) {
  // Only agents that are live today, and only the categories they actually belong to.
  const categories = ["All", ...Array.from(new Set(LIVE_AGENTS.flatMap((a) => a.category ?? [])))];
  const term = searchTerm.trim().toLowerCase();
  const searching = term.length > 0;

  const tabOk = (agent: (typeof LIVE_AGENTS)[number]) =>
    activeTab === "All" || (agent.category ?? []).includes(activeTab);
  const inSearch = (agent: (typeof LIVE_AGENTS)[number]) =>
    !term || agent.name.toLowerCase().includes(term) || agent.desc!.toLowerCase().includes(term);

  const list = LIVE_AGENTS.filter((a) => tabOk(a) && inSearch(a));
  const allTitle = searching ? `Results for "${searchTerm}"` : activeTab === "All" ? "All Agents" : `${activeTab} Agents`;

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
          {categories.map((cat) => (
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
