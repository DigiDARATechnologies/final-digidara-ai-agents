import { useState } from "react";
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
  openChatMenuId: string | null;
  onToggleCollapse: () => void;
  onNewChat: () => void;
  onGoHome: () => void;
  onOpenChat: (chatId: string) => void;
  onNavAction: (action: "my-agents" | "workflows" | "saved" | "settings") => void;
  onToggleUserMenu: (e: React.MouseEvent) => void;
  onUserMenuAction: (action: "profile" | "settings" | "logout") => void;
  onToggleChatMenu: (chatId: string, e: React.MouseEvent) => void;
  onRenameChat: (chatId: string, title: string) => void;
  onTogglePinChat: (chatId: string) => void;
  onDeleteChat: (chatId: string) => void;
}

export default function Sidebar({
  user,
  collapsed,
  mobileOpen,
  homeActive,
  chats,
  currentChatId,
  userMenuOpen,
  openChatMenuId,
  onToggleCollapse,
  onNewChat,
  onGoHome,
  onOpenChat,
  onNavAction,
  onToggleUserMenu,
  onUserMenuAction,
  onToggleChatMenu,
  onRenameChat,
  onTogglePinChat,
  onDeleteChat,
}: SidebarProps) {
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const sortedChats = [...chats].sort((a, b) => {
    if (!!a.pinned !== !!b.pinned) return a.pinned ? -1 : 1;
    return b.updatedAt - a.updatedAt;
  });

  function startRename(chat: Chat) {
    setRenamingId(chat.id);
    setRenameValue(chat.title);
  }

  function commitRename(chatId: string) {
    onRenameChat(chatId, renameValue);
    setRenamingId(null);
  }

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
            const isRenaming = renamingId === c.id;
            return (
              <div key={c.id} className={`history-item${c.id === currentChatId ? " active" : ""}`}>
                <button
                  type="button"
                  className="history-item-main"
                  onClick={() => !isRenaming && onOpenChat(c.id)}
                >
                  <span className="h-dot" style={{ background: agent.color || "#365f91" }} />
                  {isRenaming ? (
                    <input
                      className="history-rename-input"
                      autoFocus
                      value={renameValue}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onBlur={() => commitRename(c.id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitRename(c.id);
                        if (e.key === "Escape") setRenamingId(null);
                      }}
                    />
                  ) : (
                    <>
                      {c.pinned && <span className="history-pin-icon" title="Pinned">📌</span>}
                      <span className="history-title">{c.title}</span>
                    </>
                  )}
                </button>
                <div className="dropdown-wrap">
                  <button
                    type="button"
                    className="icon-btn history-menu-btn"
                    onClick={(e) => onToggleChatMenu(c.id, e)}
                    aria-label="Chat options"
                  >
                    ⋯
                  </button>
                  <div className={`dropdown-panel history-menu-panel${openChatMenuId === c.id ? " open" : ""}`}>
                    <button type="button" onClick={() => startRename(c)}>
                      ✏️ Rename
                    </button>
                    <button type="button" onClick={() => onTogglePinChat(c.id)}>
                      📌 {c.pinned ? "Unpin chat" : "Pin chat"}
                    </button>
                    <button type="button" className="danger" onClick={() => onDeleteChat(c.id)}>
                      🗑️ Delete
                    </button>
                  </div>
                </div>
              </div>
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
