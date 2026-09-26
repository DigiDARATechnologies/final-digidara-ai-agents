import type { User } from "../types";
import { AGENTS } from "../data/agents";
import type { PendingNotification } from "../lib/notifications";

interface TopbarProps {
  title: string;
  user: User;
  notifOpen: boolean;
  onToggleMobileMenu: () => void;
  onToggleNotif: (e: React.MouseEvent) => void;
  dashboardAvailable: boolean;
  dashboardOpen: boolean;
  onToggleDashboard: () => void;
  systemOnline: boolean;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  /** What is pending in each agent (see lib/notifications.ts). */
  notifications: PendingNotification[];
  onOpenNotification: (notification: PendingNotification) => void;
  onDismissNotification: (notification: PendingNotification) => void;
}

export default function Topbar({ title, user, notifOpen, onToggleMobileMenu, onToggleNotif, dashboardAvailable, dashboardOpen, onToggleDashboard, systemOnline, theme, onToggleTheme, notifications, onOpenNotification, onDismissNotification }: TopbarProps) {
  return (
    <header className="topbar">
      <button className="icon-btn mobile-only" onClick={onToggleMobileMenu} aria-label="Open menu">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>
      <div className="topbar-title">{title}</div>

      <div className="agent-ticker" aria-hidden="true">
        <div className="agent-ticker-track">
          {[0, 1].map((copy) =>
            AGENTS.map((a) => (
              <span className="agent-ticker-chip" key={`${copy}-${a.id}`} style={{ ["--chip-color" as string]: a.color }}>
                <span className="agent-ticker-icon">{a.icon}</span>
                {a.name}
              </span>
            )),
          )}
        </div>
      </div>

      <div className="topbar-right">
        {dashboardAvailable && (
          <button className={`btn dashboard-toggle${dashboardOpen ? " active" : ""}`} onClick={onToggleDashboard}>
            Dashboard
          </button>
        )}
        {!systemOnline && (
          <span className="status-pill offline">
            <span className="status-dot" /> Project agent offline
          </span>
        )}
        <button
          className="icon-btn theme-toggle"
          onClick={onToggleTheme}
          aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          title={theme === "dark" ? "Light theme" : "Dark theme"}
        >
          {theme === "dark" ? (
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="2" />
              <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          ) : (
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </button>
        <div className="dropdown-wrap">
          <button className="icon-btn" onClick={onToggleNotif} aria-label="Notifications">
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none">
              <path
                d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path d="M13.73 21a2 2 0 01-3.46 0" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
            {notifications.length > 0 && <span className="badge-dot" />}
          </button>
          <div className={`dropdown-panel${notifOpen ? " open" : ""}`}>
            <div className="dropdown-head">Notifications</div>
            {notifications.length === 0 && (
              <div className="notif-item">
                <div>
                  <b>You're all caught up</b>
                  <br />
                  Nothing is pending in any agent.
                </div>
              </div>
            )}
            {notifications.map((n) => (
              <div className="notif-item" key={n.id} role="button" tabIndex={0} style={{ cursor: "pointer" }}
                onClick={() => onOpenNotification(n)}
                onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onOpenNotification(n); } }}>
                <span className="notif-ico">{n.icon}</span>
                <div>
                  <b>{n.agentName}</b>
                  <br />
                  {n.body}
                </div>
                <button
                  type="button"
                  className="icon-btn notif-dismiss"
                  aria-label={`Dismiss ${n.agentName} notification`}
                  title="Dismiss"
                  onClick={(event) => { event.stopPropagation(); onDismissNotification(n); }}
                  onKeyDown={(event) => event.stopPropagation()}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
        <button className="avatar avatar-btn">{user.avatarUrl ? <img src={user.avatarUrl} alt="" /> : user.initial}</button>
      </div>
    </header>
  );
}
