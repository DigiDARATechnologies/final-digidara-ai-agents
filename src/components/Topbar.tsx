import type { User } from "../types";

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
}

const NOTIFICATIONS = [
  { icon: "✅", title: "Resume Builder Agent", body: "Your ATS resume is ready to download." },
  { icon: "🎯", title: "Mock Interview Agent", body: "New system-design mock scheduled today." },
  { icon: "🔥", title: "Streak", body: "You're on a 12 day learning streak!" },
];

export default function Topbar({ title, user, notifOpen, onToggleMobileMenu, onToggleNotif, dashboardAvailable, dashboardOpen, onToggleDashboard, systemOnline }: TopbarProps) {
  return (
    <header className="topbar">
      <button className="icon-btn mobile-only" onClick={onToggleMobileMenu} aria-label="Open menu">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>
      <div className="topbar-title">{title}</div>

      <div className="topbar-right">
        {dashboardAvailable && (
          <button className={`btn dashboard-toggle${dashboardOpen ? " active" : ""}`} onClick={onToggleDashboard}>
            Dashboard
          </button>
        )}
        <span className={`status-pill${systemOnline ? "" : " offline"}`}>
          <span className="status-dot" /> {systemOnline ? "Project agent connected" : "Project agent offline"}
        </span>
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
            <span className="badge-dot" />
          </button>
          <div className={`dropdown-panel${notifOpen ? " open" : ""}`}>
            <div className="dropdown-head">Notifications</div>
            {NOTIFICATIONS.map((n) => (
              <div className="notif-item" key={n.title}>
                <span className="notif-ico">{n.icon}</span>
                <div>
                  <b>{n.title}</b>
                  <br />
                  {n.body}
                </div>
              </div>
            ))}
          </div>
        </div>
        <button className="avatar avatar-btn">{user.initial}</button>
      </div>
    </header>
  );
}
