import { useEffect, useLayoutEffect, useState } from "react";
import { createPortal } from "react-dom";
import type { Chat, User } from "../types";
import { DEFAULT_AGENT, findAgent } from "../data/agents";
import { Logo } from "./Logo";
import LegalModal from "./LegalModal";
import ConfirmDialog from "./ConfirmDialog";
import blackThemeLogo from "../assets/Black_theme_logo.png";
import whiteThemeLogo from "../assets/White_theme_logo.png";

export interface SidebarProps {
  theme: "dark" | "light";
  planName: string;
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
  onOpenHelpPage: (page: "help-center" | "release-notes" | "contact" | "bug-report") => void;
  onNavAction: (action: "my-agents" | "workflows" | "saved" | "settings" | "playground" | "admin") => void;
  onToggleUserMenu: (e: React.MouseEvent) => void;
  onUserMenuAction: (action: "profile" | "settings" | "upgrade" | "logout") => void;
  onToggleChatMenu: (chatId: string, e: React.MouseEvent) => void;
  onRenameChat: (chatId: string, title: string) => void;
  onTogglePinChat: (chatId: string) => void;
  onDeleteChat: (chatId: string) => void;
}

export default function Sidebar({
  theme,
  planName,
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
  onOpenHelpPage,
  onToggleUserMenu,
  onUserMenuAction,
  onToggleChatMenu,
  onRenameChat,
  onTogglePinChat,
  onDeleteChat,
}: SidebarProps) {
  const [helpOpen, setHelpOpen] = useState(false);
  const [legalTab, setLegalTab] = useState<"terms" | "privacy" | null>(null);
  useEffect(() => {
    if (!userMenuOpen) setHelpOpen(false);
  }, [userMenuOpen]);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [chatToDelete, setChatToDelete] = useState<Chat | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [menuAnchor, setMenuAnchor] = useState<HTMLButtonElement | null>(null);
  const [menuPosition, setMenuPosition] = useState({ top: 0, left: 0 });

  const sortedChats = [...chats].sort((a, b) => {
    if (!!a.pinned !== !!b.pinned) return a.pinned ? -1 : 1;
    return b.updatedAt - a.updatedAt;
  });
  const openMenuChat = sortedChats.find((chat) => chat.id === openChatMenuId);

  useLayoutEffect(() => {
    if (!openChatMenuId || !menuAnchor) return;

    const positionMenu = () => {
      const rect = menuAnchor.getBoundingClientRect();
      const menuWidth = 170;
      const menuHeight = 132;
      const viewportGap = 8;
      const top = rect.bottom + 4 + menuHeight <= window.innerHeight
        ? rect.bottom + 4
        : Math.max(viewportGap, rect.top - menuHeight - 4);

      setMenuPosition({
        top,
        left: Math.min(
          window.innerWidth - menuWidth - viewportGap,
          Math.max(viewportGap, rect.right - menuWidth),
        ),
      });
    };

    positionMenu();
    window.addEventListener("resize", positionMenu);
    document.addEventListener("scroll", positionMenu, true);
    return () => {
      window.removeEventListener("resize", positionMenu);
      document.removeEventListener("scroll", positionMenu, true);
    };
  }, [openChatMenuId, menuAnchor]);

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
          <Logo
            variant={collapsed ? "icon" : "full"}
            size={collapsed ? 36 : 66}
            src={collapsed ? undefined : theme === "dark" ? blackThemeLogo : whiteThemeLogo}
          />
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
        <span className="nav-icon glow-icon">
          <svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M3.5 10.8L12 3.5l8.5 7.3V20a1 1 0 01-1 1H15v-6h-6v6H4.5a1 1 0 01-1-1v-9.2z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
          </svg>
        </span>
        <span className="label">DigiDARA Agents</span>
      </button>

      <nav className="nav-list">
        <button className="nav-item" onClick={() => onNavAction("my-agents")}>
          <span className="nav-icon">
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <rect x="3.5" y="3.5" width="7" height="7" rx="1.8" stroke="currentColor" strokeWidth="1.7" />
              <rect x="13.5" y="3.5" width="7" height="7" rx="1.8" stroke="currentColor" strokeWidth="1.7" />
              <rect x="3.5" y="13.5" width="7" height="7" rx="1.8" stroke="currentColor" strokeWidth="1.7" />
              <rect x="13.5" y="13.5" width="7" height="7" rx="1.8" stroke="currentColor" strokeWidth="1.7" />
            </svg>
          </span>
          <span className="label">My agents</span>
        </button>
        <button className="nav-item" onClick={() => onNavAction("workflows")}>
          <span className="nav-icon">
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="6" cy="6" r="2.4" stroke="currentColor" strokeWidth="1.7" />
              <circle cx="6" cy="18" r="2.4" stroke="currentColor" strokeWidth="1.7" />
              <circle cx="18" cy="12" r="2.4" stroke="currentColor" strokeWidth="1.7" />
              <path d="M6 8.4v7.2M8.4 6h3.1a3 3 0 013 3v.6M8.4 18h3.1a3 3 0 003-3v-.6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
            </svg>
          </span>
          <span className="label">Workflows</span>
        </button>
        <button className="nav-item" onClick={() => onNavAction("saved")}>
          <span className="nav-icon">
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M6.5 3.5h11a1 1 0 011 1V21l-6.5-4.4L5.5 21V4.5a1 1 0 011-1z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
            </svg>
          </span>
          <span className="label">Saved work</span>
        </button>
        <button className="nav-item" onClick={() => onNavAction("settings")}>
          <span className="nav-icon">
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.7" />
              <path d="M19.4 15a1.7 1.7 0 00.34 1.87l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.7 1.7 0 00-1.87-.34 1.7 1.7 0 00-1 1.55V21a2 2 0 11-4 0v-.09a1.7 1.7 0 00-1.1-1.55 1.7 1.7 0 00-1.87.34l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.7 1.7 0 00.34-1.87 1.7 1.7 0 00-1.55-1H3a2 2 0 110-4h.09a1.7 1.7 0 001.55-1.1 1.7 1.7 0 00-.34-1.87l-.06-.06a2 2 0 112.83-2.83l.06.06a1.7 1.7 0 001.87.34h0a1.7 1.7 0 001-1.55V3a2 2 0 114 0v.09a1.7 1.7 0 001 1.55h0a1.7 1.7 0 001.87-.34l.06-.06a2 2 0 112.83 2.83l-.06.06a1.7 1.7 0 00-.34 1.87v0a1.7 1.7 0 001.55 1H21a2 2 0 110 4h-.09a1.7 1.7 0 00-1.55 1z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
            </svg>
          </span>
          <span className="label">Settings</span>
        </button>
        <button className="nav-item" onClick={() => onNavAction("playground")}>
          <span className="nav-icon">
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M8.5 7L3.5 12l5 5M15.5 7l5 5-5 5M13.5 5l-3 14" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <span className="label">Code Playground</span>
        </button>
        {user.isAdmin && (
          <button className="nav-item" onClick={() => onNavAction("admin")}>
            <span className="nav-icon">
              <svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M12 3l7.5 3v5.5c0 4.5-3.1 8.2-7.5 9.5-4.4-1.3-7.5-5-7.5-9.5V6L12 3z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
                <path d="M8.8 12.2l2.2 2.2 4.2-4.4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            <span className="label">Admin</span>
          </button>
        )}
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
              <div key={c.id} className={`history-item${c.id === currentChatId ? " active" : ""}${openChatMenuId === c.id ? " menu-open" : ""}`}>
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
                <button
                  type="button"
                  className="icon-btn history-menu-btn"
                  onClick={(e) => {
                    setMenuAnchor(e.currentTarget);
                    onToggleChatMenu(c.id, e);
                  }}
                  aria-label="Chat options"
                  aria-haspopup="menu"
                  aria-expanded={openChatMenuId === c.id}
                >
                  ⋯
                </button>
              </div>
            );
          })
        )}
      </div>

      {openMenuChat && menuAnchor && !chatToDelete && createPortal(
        <div
          className="dropdown-panel history-menu-panel open history-menu-floating"
          style={{ top: menuPosition.top, left: menuPosition.left }}
          role="menu"
        >
          <button type="button" role="menuitem" onClick={() => startRename(openMenuChat)}>
            ✏️ Rename
          </button>
          <button type="button" role="menuitem" onClick={() => onTogglePinChat(openMenuChat.id)}>
            📌 {openMenuChat.pinned ? "Unpin chat" : "Pin chat"}
          </button>
          <button type="button" role="menuitem" className="danger" onClick={() => setChatToDelete(openMenuChat)}>
            🗑️ Delete
          </button>
        </div>,
        document.body,
      )}

      {chatToDelete && (
        <ConfirmDialog
          title="Delete this chat?"
          message={`"${chatToDelete.title}" and its messages will be deleted. This cannot be undone.`}
          confirmLabel="Delete"
          onCancel={() => setChatToDelete(null)}
          onConfirm={() => { onDeleteChat(chatToDelete.id); setChatToDelete(null); }}
        />
      )}

      <div className="sidebar-bottom">
        <button className="user-chip" onClick={onToggleUserMenu}>
          <span className="avatar">{user.avatarUrl ? <img src={user.avatarUrl} alt="" /> : user.initial}</span>
          <span className="user-meta label">
            <span className="user-name-row">
              <span className="user-name">{user.name}</span>
              <span className={`plan-badge${planName === "Free" ? " free" : ""}`}>{planName}</span>
            </span>
            <span className="user-plan">{user.email}</span>
          </span>
          <svg className="label" width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        <div className={`user-menu${userMenuOpen ? " open" : ""}`}>
          <div className="user-menu-head">
            <span className="avatar">{user.avatarUrl ? <img src={user.avatarUrl} alt="" /> : user.initial}</span>
            <span className="user-menu-id">
              <span className="user-menu-name">{user.name}</span>
              <span className="user-menu-plan">{planName} plan</span>
            </span>
          </div>
          <div className="user-menu-sep" />
          <button onClick={() => onUserMenuAction("upgrade")}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M12 3.5l2.2 5.3 5.3 2.2-5.3 2.2L12 18.5l-2.2-5.3L4.5 11l5.3-2.2L12 3.5z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
            </svg>
            {planName === "Free" ? "Upgrade plan" : "Manage plan"}
          </button>
          <button onClick={() => onUserMenuAction("profile")}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.7" />
              <circle cx="12" cy="10" r="3" stroke="currentColor" strokeWidth="1.7" />
              <path d="M6.2 18.2c1.4-2.3 3.4-3.2 5.8-3.2s4.4.9 5.8 3.2" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
            </svg>
            Profile
          </button>
          <button onClick={() => onUserMenuAction("settings")}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.7" />
              <path d="M19.4 15a1.7 1.7 0 00.34 1.87l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.7 1.7 0 00-1.87-.34 1.7 1.7 0 00-1 1.55V21a2 2 0 11-4 0v-.09a1.7 1.7 0 00-1.1-1.55 1.7 1.7 0 00-1.87.34l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.7 1.7 0 00.34-1.87 1.7 1.7 0 00-1.55-1H3a2 2 0 110-4h.09a1.7 1.7 0 001.55-1.1 1.7 1.7 0 00-.34-1.87l-.06-.06a2 2 0 112.83-2.83l.06.06a1.7 1.7 0 001.87.34h0a1.7 1.7 0 001-1.55V3a2 2 0 114 0v.09a1.7 1.7 0 001 1.55h0a1.7 1.7 0 001.87-.34l.06-.06a2 2 0 112.83 2.83l-.06.06a1.7 1.7 0 00-.34 1.87v0a1.7 1.7 0 001.55 1H21a2 2 0 110 4h-.09a1.7 1.7 0 00-1.55 1z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
            </svg>
            Settings
          </button>
          <div className="user-menu-sep" />
          <div className={`user-menu-help${helpOpen ? " open" : ""}`}>
            <button
              type="button"
              className="user-menu-help-trigger"
              aria-haspopup="menu"
              aria-expanded={helpOpen}
              onClick={(e) => {
                e.stopPropagation();
                setHelpOpen((v) => !v);
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.7" />
                <circle cx="12" cy="12" r="3.6" stroke="currentColor" strokeWidth="1.7" />
                <path d="M5.6 5.6l3.9 3.9M14.5 14.5l3.9 3.9M18.4 5.6l-3.9 3.9M9.5 14.5l-3.9 3.9" stroke="currentColor" strokeWidth="1.7" />
              </svg>
              <span className="user-menu-grow">Help</span>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M9 6l6 6-6 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <div className="user-menu-flyout" role="menu">
              <button type="button" role="menuitem" onClick={() => onOpenHelpPage("help-center")}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.7" />
                  <path d="M9.6 9.4a2.5 2.5 0 114 2c-.9.6-1.6 1.1-1.6 2.1M12 16.9v.1" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
                </svg>
                Help center
              </button>
              <button type="button" role="menuitem" onClick={() => onOpenHelpPage("release-notes")}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M4 20l1.2-4.2L16.5 4.5a2 2 0 012.8 0l.2.2a2 2 0 010 2.8L8.2 18.8 4 20zM14.5 6.5l3 3" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                Release notes
              </button>
              <div className="user-menu-sep" />
              <button type="button" role="menuitem" onClick={() => onOpenHelpPage("contact")}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <rect x="3.5" y="5.5" width="17" height="13" rx="2.2" stroke="currentColor" strokeWidth="1.7" />
                  <path d="M4 7.5l8 6 8-6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                Contact support
              </button>
              <button type="button" role="menuitem" onClick={() => setLegalTab("terms")}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M7 3.5h7l4 4V20a1 1 0 01-1 1H7a1 1 0 01-1-1V4.5a1 1 0 011-1z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
                  <path d="M9 12h6M9 16h6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
                </svg>
                Terms of Service
              </button>
              <button type="button" role="menuitem" onClick={() => setLegalTab("privacy")}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M12 3l7.5 3v5.5c0 4.5-3.1 8.2-7.5 9.5-4.4-1.3-7.5-5-7.5-9.5V6L12 3z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
                </svg>
                Privacy Policy
              </button>
              <div className="user-menu-sep" />
              <button type="button" role="menuitem" onClick={() => onOpenHelpPage("bug-report")}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <rect x="8" y="8" width="8" height="11" rx="4" stroke="currentColor" strokeWidth="1.7" />
                  <path d="M9.5 8a2.5 2.5 0 015 0M4 12h4M16 12h4M5 18l3-2M19 18l-3-2M5 6l3 2M19 6l-3 2" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
                </svg>
                Report a bug
              </button>
            </div>
          </div>
          <button onClick={() => onUserMenuAction("logout")}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M9 4H6a2 2 0 00-2 2v12a2 2 0 002 2h3M16 8l4 4-4 4M20 12H9" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Log out
          </button>
        </div>
      </div>
      {legalTab && createPortal(<LegalModal key={legalTab} open initialTab={legalTab} onClose={() => setLegalTab(null)} />, document.body)}
    </aside>
  );
}
