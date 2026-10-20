import type { User } from "../types";
import { LIVE_AGENTS } from "../data/agents";
import type { PendingNotification } from "../lib/notifications";
import AgentIcon from "./AgentIcon";

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
  /** What is pending in each agent (see lib/notifications.ts). */
  notifications: PendingNotification[];
  onOpenNotification: (notification: PendingNotification) => void;
  onDismissNotification: (notification: PendingNotification) => void;
}

export default function Topbar({ title, notifOpen, onToggleMobileMenu, onToggleNotif, dashboardAvailable, dashboardOpen, onToggleDashboard, systemOnline, notifications, onOpenNotification, onDismissNotification }: TopbarProps) {
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
            LIVE_AGENTS.map((a) => (
              <span className="agent-ticker-chip" key={`${copy}-${a.id}`} style={{ ["--chip-color" as string]: a.color }}>
                <span className="agent-ticker-icon"><AgentIcon name={a.icon} /></span>
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
            <span className="status-dot" /> Project Agent Offline
          </span>
        )}
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
                <span className="notif-ico"><AgentIcon name={n.icon} /></span>
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
      </div>
    </header>
  );
}
