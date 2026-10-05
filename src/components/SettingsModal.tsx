import { useEffect, useState } from "react";
import type { Chat, User } from "../types";
import { LIVE_AGENTS } from "../data/agents";
import { fetchAllUsageSummaries, type AgentUsageResult } from "../lib/usageApi";
import { fetchMonthlyUsage, type MonthlyUsage } from "../lib/billingApi";
import { formatPoints, tokensToPoints } from "../lib/points";
import ConfirmDialog from "./ConfirmDialog";
import BillingPanel from "./BillingPanel";
import { getDisplayRating } from "../lib/ratings";
import { AppearanceSettings, SecuritySettings } from "./SettingsExtras";
import type { AppearancePrefs, ThemePref } from "../lib/appearance";
import { bridgeIdentity, getDashboard, getHistory, type DashboardData } from "../lib/communicationApi";

interface Props { themePref?: ThemePref; onThemeChange?: (pref: ThemePref) => void; appearance?: AppearancePrefs; onAppearanceChange?: (next: AppearancePrefs) => void; onLogout?: () => void; initialTab?: Tab; open: boolean; user: User; chats: Chat[]; glowOn: boolean; onClose: () => void; onOpenChat: (chatId: string) => void; onGlowToggle: (on: boolean) => void; onClearHistory: () => void; onToast: (message: string) => void; onExportData: () => Promise<void>; onDeleteAccount: (password?: string) => Promise<string | null>; }
type Tab = "general" | "appearance" | "security" | "billing" | "usage" | "agent-chats";

export default function SettingsModal({ themePref = "dark", onThemeChange = () => {}, appearance = { accent: "blue", reduceMotion: false }, onAppearanceChange = () => {}, onLogout, initialTab = "general", open, user, chats, glowOn, onClose, onOpenChat, onGlowToggle, onClearHistory, onToast, onExportData, onDeleteAccount }: Props) {
  const [tab, setTab] = useState<Tab>("general"); const [usage, setUsage] = useState<AgentUsageResult[] | null>(null); const [detailAgentId, setDetailAgentId] = useState<string | null>(null); const [agentSearch, setAgentSearch] = useState(""); 
  useEffect(() => { if (open) setTab(initialTab); }, [open, initialTab]);
  const [exporting, setExporting] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [deleting, setDeleting] = useState(false);
  useEffect(() => { if (!open) return; fetchAllUsageSummaries().then(setUsage); }, [open]);
  const [monthly, setMonthly] = useState<MonthlyUsage | null>(null);
  useEffect(() => { if (!open) return; fetchMonthlyUsage().then(setMonthly).catch(() => setMonthly(null)); }, [open]);
  const [coachProgress, setCoachProgress] = useState<{ dashboard: DashboardData; history: Array<Record<string, any>> } | null>(null);
  const [coachProgressLoading, setCoachProgressLoading] = useState(false);
  // This month only, from the gateway's billing record, in points (the server
  // converts at the account's own rate). There is no fixed quota: the limit is
  // what the user had to spend this month (used + left).
  const monthPoints = monthly?.points_used ?? 0; const monthRequests = monthly?.requests ?? 0;
  const monthlyLimit = monthly?.points_limit ?? 0;
  const usagePercent = monthlyLimit > 0 ? Math.min(100, Math.round((monthPoints / monthlyLimit) * 100)) : 0;
  const monthLabel = new Date(monthly?.month_start ?? Date.now()).toLocaleDateString([], { month: "long", year: "numeric" });
  const monthOfAgent = (id: string) => monthly?.agents.find((row) => row.agent_name === id);
  // Only agents that are actually built (they have a backend flow); the placeholder cards are not listed here.
  const agentChatRows = LIVE_AGENTS.map((agent) => {
    const agentChats = chats.filter((chat) => chat.agentId === agent.id).sort((a, b) => b.updatedAt - a.updatedAt);
    const agentUsage = usage?.find((item) => item.id === agent.backendAgentName);
    return { agent, chats: agentChats, usage: agentUsage, requests: agentUsage?.usage?.total_requests ?? 0, lastUsed: agentChats[0]?.updatedAt ?? null };
  });
  const detailRow = agentChatRows.find((row) => row.agent.id === detailAgentId);
  const filteredAgentChatRows = agentChatRows.filter(({ agent }) => {
    const term = agentSearch.trim().toLowerCase();
    return !term || agent.name.toLowerCase().includes(term) || (agent.desc ?? "").toLowerCase().includes(term) || (agent.author ?? "").toLowerCase().includes(term) || agent.category?.some((category) => category.toLowerCase().includes(term));
  });

  useEffect(() => {
    if (!open || detailAgentId !== "communication-coach") return;
    let active = true;
    setCoachProgressLoading(true);
    bridgeIdentity(user.name, user.email)
      .then(({ authToken }) => Promise.all([getDashboard(authToken), getHistory(authToken)]))
      .then(([dashboard, history]) => { if (active) setCoachProgress({ dashboard, history: history.items }); })
      .catch(() => { if (active) setCoachProgress(null); })
      .finally(() => { if (active) setCoachProgressLoading(false); });
    return () => { active = false; };
  }, [open, detailAgentId, user.name, user.email]);

  async function handleExport() {
    setExporting(true);
    try { await onExportData(); } finally { setExporting(false); }
  }

  async function confirmDelete() {
    setDeleting(true);
    setDeleteError("");
    const result = await onDeleteAccount(deletePassword || undefined);
    setDeleting(false);
    if (result) { setDeleteError(result); return; }
    setDeleteConfirmOpen(false);
  }

  return <div className={`modal-overlay${open ? " open" : ""}`} onClick={(event) => event.target === event.currentTarget && onClose()}>
    <div className="modal-card settings-shell">
      <aside className="settings-nav"><button className="settings-close" onClick={onClose}>×</button><h3>Settings</h3>{(["general", "appearance", "security", "billing", "usage", "agent-chats"] as Tab[]).map((item) => <button key={item} className={tab === item ? "active" : ""} onClick={() => setTab(item)}><span>{item === "general" ? "⚙" : item === "appearance" ? "◐" : item === "security" ? "⚿" : item === "billing" ? "▣" : item === "usage" ? "▤" : "◫"}</span>{item === "agent-chats" ? "Agent Chats" : item[0].toUpperCase() + item.slice(1)}</button>)}</aside>
      <main className="settings-content">
        {tab === "general" && <><h2>General</h2><div className="settings-section"><div className="setting-row"><div><b>Profile</b><p>{user.name}<br />{user.email} · {user.mobile}</p></div></div><div className="setting-row"><div><b>Accent Glow Effects</b><p>Toggle animated glow on cards and buttons.</p></div><label className="switch"><input type="checkbox" checked={glowOn} onChange={(event) => onGlowToggle(event.target.checked)} /><span className="slider" /></label></div><div className="setting-row"><div><b>Clear Chat History</b><p>Remove all saved conversations for this account.</p></div><button className="btn btn-outline btn-danger" onClick={() => setClearConfirmOpen(true)}>Clear</button></div></div>
          <h3 className="settings-title">Privacy &amp; data</h3>
          <p className="settings-subtitle">Your rights under the Digital Personal Data Protection Act, 2023.</p>
          <div className="settings-section">
            <div className="setting-row"><div><b>Download My Data</b><p>Get a JSON copy of every piece of personal data DigiDARA holds about your account — the DPDP right to access.</p></div><button className="btn btn-outline" disabled={exporting} onClick={handleExport}>{exporting ? "Preparing…" : "Download"}</button></div>
            <div className="setting-row"><div><b>Delete My Account</b><p>Permanently erase your account and personal data. This also withdraws your consent to processing and cannot be undone.</p></div><button className="btn btn-outline btn-danger" onClick={() => { setDeleteConfirmOpen(true); setDeleteError(""); setDeletePassword(""); }}>Delete Account</button></div>
            <div className="setting-row"><div><b>Grievance Officer</b><p>Questions or complaints about how your data is handled: <a href="mailto:support@digidaratechnologies.com">support@digidaratechnologies.com</a>.</p></div></div>
          </div></>}
        {tab === "appearance" && <AppearanceSettings themePref={themePref} onThemeChange={onThemeChange} appearance={appearance} onAppearanceChange={onAppearanceChange} glowOn={glowOn} onGlowToggle={onGlowToggle} />}
        {tab === "security" && <SecuritySettings user={user} onToast={onToast} onLogout={onLogout} />}
        {tab === "billing" && <BillingPanel open={open} user={user} onToast={onToast} />}
        {tab === "usage" && <><h2>Usage</h2><p className="settings-subtitle">Track usage across your DigiDARA agents.</p><div className="settings-usage-summary"><div className="settings-platform-total"><span>Your Usage · {monthLabel}</span><strong>{formatPoints(monthPoints)} points</strong><small>· {monthRequests} requests</small></div><div className="profile-usage-limit"><div><b>Monthly Usage</b><span>{monthly ? `${100 - usagePercent}% remaining` : "Not available"}</span></div><div className="usage-progress"><span style={{ width: `${usagePercent}%` }} /></div><small>{monthly ? `${formatPoints(monthPoints)} of ${formatPoints(monthlyLimit)} points used this month` : "Monthly usage could not be loaded."}</small></div></div><h3 className="settings-title">Agent Usage · {monthLabel}</h3><div className="usage-settings-list">{usage?.map((item) => { const month = monthOfAgent(item.id); return <div key={item.id}><span className="profile-agent-icon" style={{ background: item.color }}>{item.icon}</span><span><b>{item.label}</b><small>{monthly ? `${formatPoints(month?.points ?? 0)} points · ${month?.requests ?? 0} requests` : "Not available"}</small></span><i className={!item.tracked ? "idle" : item.online ? "" : "offline"} /></div>; }) ?? <p>Loading usage…</p>}</div></>}
        {tab === "agent-chats" && <><h2>Agent Chats</h2><p className="settings-subtitle">Conversation activity and request history for every agent.</p><label className="agent-chat-search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></svg><input value={agentSearch} onChange={(event) => setAgentSearch(event.target.value)} placeholder="Search agents by name, category or capability…" /><span>{filteredAgentChatRows.length} agents</span>{agentSearch && <button onClick={() => setAgentSearch("")} aria-label="Clear search">×</button>}</label><div className="agent-chat-table">{filteredAgentChatRows.map(({ agent, chats: agentChats, requests, lastUsed }) => <article key={agent.id}><span className="agent-chat-icon" style={{ background: agent.color }}>{agent.icon}</span><div className="agent-chat-main"><b>{agent.name}</b><small>{agent.desc}</small></div><div className="agent-chat-metric"><b>{requests}</b><small>requests</small></div><div className="agent-chat-metric"><b>{agentChats.length}</b><small>chats</small></div><div className="agent-chat-last"><b>{lastUsed ? new Date(lastUsed).toLocaleDateString() : "Never"}</b><small>{lastUsed ? new Date(lastUsed).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "Not used"}</small></div><button onClick={() => setDetailAgentId(agent.id)}>More Details</button></article>)}{filteredAgentChatRows.length === 0 && <div className="agent-chat-empty">No agents match “{agentSearch}”.</div>}</div></>}
      </main>
      {detailRow && <div className="agent-chat-detail"><div className="agent-chat-detail-head"><button onClick={() => setDetailAgentId(null)}>← Back</button><span>Agent Details</span><button onClick={() => setDetailAgentId(null)}>×</button></div><div className="agent-chat-detail-body"><header><span className="agent-detail-mini-icon" style={{ background: detailRow.agent.color }}>{detailRow.agent.icon}</span><div><h2>{detailRow.agent.name}</h2><p>{detailRow.agent.desc}</p></div><span className={`agent-health${detailRow.usage?.online ? "" : " offline"}`}>{detailRow.usage?.online ? "Online" : "Offline"}</span></header><div className="agent-detail-cards"><article><span>Total Chats</span><strong>{detailRow.chats.length}</strong><small>Saved Conversations</small></article><article><span>Requests</span><strong>{detailRow.requests}</strong><small>Agent Executions</small></article><article><span>Pending</span><strong>{detailRow.chats.filter((chat) => chat.messages.filter((message) => message.role === "user").length <= 1).length}</strong><small>Early-Stage Chats</small></article><article><span>Completed</span><strong>{detailRow.chats.filter((chat) => chat.messages.filter((message) => message.role === "user").length > 1).length}</strong><small>Multi-Turn Chats</small></article></div><section className="agent-detail-info"><h3>Activity Information</h3><dl><div><dt>Last Used</dt><dd>{detailRow.lastUsed ? new Date(detailRow.lastUsed).toLocaleString() : "Never used"}</dd></div><div><dt>Total Messages</dt><dd>{detailRow.chats.reduce((sum, chat) => sum + chat.messages.length, 0)}</dd></div><div><dt>Points Used</dt><dd>{formatPoints(tokensToPoints(detailRow.usage?.usage?.total_tokens ?? 0, monthly?.tokens_per_point))}</dd></div><div><dt>Category</dt><dd>{detailRow.agent.category?.filter((item) => item !== "Top Picks").join(", ") || "General"}</dd></div><div><dt>Agent Rating</dt><dd>★ {getDisplayRating(detailRow.agent.id, detailRow.agent.rating).value.toFixed(1)}</dd></div></dl></section>{detailRow.agent.id === "communication-coach" && <section className="coach-progress-detail"><h3>Progress & Scores</h3>{coachProgressLoading ? <p>Loading progress…</p> : coachProgress ? <><div className="coach-score-grid"><article><span>Overall</span><strong>{coachProgress.dashboard.overall_score ?? "—"}/10</strong></article><article><span>Speaking</span><strong>{coachProgress.dashboard.speaking_average ?? "—"}/10</strong><small>{coachProgress.dashboard.speaking_completed} sessions</small></article><article><span>Writing</span><strong>{coachProgress.dashboard.writing_average ?? "—"}/10</strong><small>{coachProgress.dashboard.writing_completed} sessions</small></article><article><span>Pronunciation</span><strong>{coachProgress.dashboard.pronunciation_average ?? "—"}/10</strong><small>{coachProgress.dashboard.pronunciation_completed} sessions</small></article></div><div className="coach-history-list"><h3>Practice History</h3>{coachProgress.history.length ? coachProgress.history.slice(0, 8).map((item, index) => <div key={`${item.type ?? "session"}-${item.session_id ?? index}`}><span><b>{item.topic_title ?? item.title ?? "Practice session"}</b><small>{item.type ?? "Practice"}{item.completed_at ? ` · ${new Date(item.completed_at).toLocaleString()}` : ""}</small></span><strong>{item.overall_score ?? "—"}/10</strong></div>) : <p>No completed practice sessions yet.</p>}</div></> : <p>Progress is unavailable right now.</p>}</section>}<section className="recent-agent-chats"><h3>Recent Chats</h3>{detailRow.chats.length ? detailRow.chats.slice(0, 8).map((chat) => { const userTurns = chat.messages.filter((message) => message.role === "user").length; return <button key={chat.id} onClick={() => onOpenChat(chat.id)}><span><b>{chat.title}</b><small>{chat.messages.length} messages · {new Date(chat.updatedAt).toLocaleString()}</small></span><i className={userTurns > 1 ? "completed" : "pending"}>{userTurns > 1 ? "Completed" : "Pending"}</i><em>›</em></button>; }) : <p>No conversations with this agent yet.</p>}</section></div></div>}
    </div>
    {clearConfirmOpen && <ConfirmDialog title="Clear all chat history?" message="Every saved conversation for this account will be deleted. This cannot be undone." confirmLabel="Clear all" onCancel={() => setClearConfirmOpen(false)} onConfirm={() => { setClearConfirmOpen(false); onClearHistory(); }} />}
    {deleteConfirmOpen && <div className="modal-overlay open" onClick={(event) => event.target === event.currentTarget && !deleting && setDeleteConfirmOpen(false)}>
      <div className="modal-card" style={{ maxWidth: 420 }}>
        <div className="modal-head"><h3>Delete your account?</h3><button type="button" className="icon-btn" aria-label="Close" onClick={() => setDeleteConfirmOpen(false)}>✕</button></div>
        <div className="modal-body">
          <p>This permanently erases your DigiDARA account and personal data — name, email, mobile, and consent record — and withdraws your consent to processing. It cannot be undone.</p>
          <label className="field"><span>Confirm Your Password</span><input type="password" placeholder="Leave blank if you only sign in with Google" value={deletePassword} onChange={(event) => setDeletePassword(event.target.value)} /></label>
          {deleteError && <p className="form-error" role="alert">{deleteError}</p>}
          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 16 }}>
            <button className="btn btn-outline" onClick={() => setDeleteConfirmOpen(false)} disabled={deleting}>Cancel</button>
            <button className="btn btn-outline btn-danger" onClick={confirmDelete} disabled={deleting}>{deleting ? "Deleting…" : "Delete permanently"}</button>
          </div>
        </div>
      </div>
    </div>}
  </div>;
}
