import { useState } from "react";
import type { User } from "../types";
import { ADMIN_PANELS } from "../data/adminPanels";
import JobsAdminPanel from "./admin/JobsAdminPanel";
import AdminChangePassword from "./admin/AdminChangePassword";

interface AdminShellProps {
  user: User;
  onBack: () => void;
}

/** Platform-wide admin shell: reached from Sidebar's "Admin" nav item, shown
 * only when `user.isAdmin` is true (see App.tsx's handleNavAction). Every
 * panel here calls its own agent through the same orchestrator gateway the
 * student chat uses — the only difference is the verified
 * X-Digidara-Is-Admin header the gateway forwards for this user. Adding a
 * future agent's admin panel means one more entry in data/adminPanels.ts and
 * one more case below; no other agent's files change. */
export default function AdminShell({ user, onBack }: AdminShellProps) {
  const [activePanelId, setActivePanelId] = useState(ADMIN_PANELS[0]?.id ?? "");

  return (
    <div className="admin-shell">
      <aside className="admin-shell-nav">
        <button className="btn btn-outline btn-sm admin-back-btn" onClick={onBack}>← Back</button>
        <div className="admin-shell-title">Admin</div>
        <nav>
          {ADMIN_PANELS.map((panel) => (
            <button
              key={panel.id}
              className={`admin-shell-nav-item${panel.id === activePanelId ? " active" : ""}`}
              onClick={() => setActivePanelId(panel.id)}
            >
              <span>{panel.icon}</span>
              <span>{panel.label}</span>
            </button>
          ))}
        </nav>
        <div className="admin-shell-user">
          Signed in as {user.name}
          <AdminChangePassword />
        </div>
      </aside>
      <main className="admin-shell-content">
        {ADMIN_PANELS.find((p) => p.id === activePanelId) ? (
          <>
            <div className="admin-shell-content-head">
              <h2>{ADMIN_PANELS.find((p) => p.id === activePanelId)!.label}</h2>
              <p>{ADMIN_PANELS.find((p) => p.id === activePanelId)!.desc}</p>
            </div>
            {activePanelId === "job-agent" && <JobsAdminPanel />}
          </>
        ) : (
          <p>No admin panels are registered yet.</p>
        )}
      </main>
    </div>
  );
}

