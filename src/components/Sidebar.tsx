import type { Chat, User } from "../types";
import { DEFAULT_AGENT, findAgent } from "../data/agents";

interface SidebarProps {
  user: User;
  collapsed: boolean;
  mobileOpen: boolean;
  homeActive: boolean;
  chats: Chat[];
  currentChatId: string | null;
  userMenuOpen: boolean;
  onToggleCollapse: () => void;
  onNewChat: () => void;
  onGoHome: () => void;
  onOpenChat: (chatId: string) => void;
  onNavAction: (action: "my-agents" | "workflows" | "saved" | "settings" | "playground") => void;
  onToggleUserMenu: (e: React.MouseEvent) => void;
  onUserMenuAction: (action: "profile" | "settings" | "logout") => void;
}

export default function Sidebar({
  user,
  collapsed,
  mobileOpen,
  homeActive,
  chats,
  currentChatId,
  userMenuOpen,
  onToggleCollapse,
  onNewChat,
  onGoHome,
  onOpenChat,
  onNavAction,
  onToggleUserMenu,
  onUserMenuAction,
}: SidebarProps) {
  const sortedChats = [...chats].sort((a, b) => b.updatedAt - a.updatedAt);

  return (
    <aside className={`sidebar${collapsed ? " collapsed" : ""}${mobileOpen ? " mobile-open" : ""}`} id="sidebar">
      <div className="sidebar-top">
        <div className="brand">
          <span className="logo-mark small">⚡</span>
          <span className="brand-text">
            Digi<b>DARA</b>
          </span>
        </div>
        <button className="icon-btn" onClick={onToggleCollapse} title="Collapse sidebar" aria-label="Collapse sidebar">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M15 6l-6 6 6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>

      <button className="btn btn-outline btn-full new-chat-btn" onClick={onNewChat}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
          <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
        <span className="label">New chat</span>
      </button>

      <button
        className={`nav-item nav-item-primary${homeActive ? " active" : ""}`}
        onClick={onGoHome}
      >
        <span className="nav-icon glow-icon">🏠</span>
        <span className="label">DigiDARA Agents</span>
      </button>

      <nav className="nav-list">
        <button className="nav-item" onClick={() => onNavAction("my-agents")}>
          <span className="nav-icon">🧩</span>
          <span className="label">My agents</span>
        </button>
        <button className="nav-item" onClick={() => onNavAction("workflows")}>
          <span className="nav-icon">🔀</span>
          <span className="label">Workflows</span>
        </button>
        <button className="nav-item" onClick={() => onNavAction("saved")}>
          <span className="nav-icon">🔖</span>
          <span className="label">Saved work</span>
        </button>
        <button className="nav-item" onClick={() => onNavAction("settings")}>
          <span className="nav-icon">⚙️</span>
          <span className="label">Settings</span>
        </button>
        <button className="nav-item" onClick={() => onNavAction("playground")}>
          <span className="nav-icon">▶</span>
          <span className="label">Code Playground</span>
        </button>
      </nav>

      <div className="sidebar-divider">
        <span className="label">History</span>
        <span className="history-count label">{sortedChats.length}</span>
      </div>

      <div className="history-list" id="historyList">
        {sortedChats.length === 0 ? (
          <div className="history-empty">
            No conversations yet.
            <br />
            Open an agent to get started.
          </div>
        ) : (
          sortedChats.map((c) => {
            const agent = findAgent(c.agentId) || DEFAULT_AGENT;
            return (
              <button
                key={c.id}
                className={`history-item${c.id === currentChatId ? " active" : ""}`}
                onClick={() => onOpenChat(c.id)}
              >
                <span className="h-dot" style={{ background: agent.color || "#6d5bff" }} />
                <span className="history-title">{c.title}</span>
              </button>
            );
          })
        )}
      </div>

      <div className="sidebar-bottom">
        <button className="user-chip" onClick={onToggleUserMenu}>
          <span className="avatar">{user.initial}</span>
          <span className="user-meta label">
            <span className="user-name">{user.name}</span>
            <span className="user-plan">⚡ Pro Plan</span>
          </span>
          <svg className="label" width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        <div className={`user-menu${userMenuOpen ? " open" : ""}`}>
          <button onClick={() => onUserMenuAction("profile")}>👤 Profile</button>
          <button onClick={() => onUserMenuAction("settings")}>⚙️ Settings</button>
          <button className="danger" onClick={() => onUserMenuAction("logout")}>
            🚪 Log out
          </button>
        </div>
      </div>
    </aside>
  );
}
