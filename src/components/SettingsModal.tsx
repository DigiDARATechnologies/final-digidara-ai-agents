import { useEffect, useState } from "react";
import type { Chat, User } from "../types";
import { AGENTS } from "../data/agents";
import { fetchAllUsageSummaries, type AgentUsageResult } from "../lib/usageApi";
import ConfirmDialog from "./ConfirmDialog";
import BillingPanel from "./BillingPanel";
import { AppearanceSettings, SecuritySettings } from "./SettingsExtras";
import type { AppearancePrefs, ThemePref } from "../lib/appearance";
import { bridgeIdentity, getDashboard, getHistory, type DashboardData } from "../lib/communicationApi";

interface Props { themePref?: ThemePref; onThemeChange?: (pref: ThemePref) => void; appearance?: AppearancePrefs; onAppearanceChange?: (next: AppearancePrefs) => void; onLogout?: () => void; initialTab?: Tab; open: boolean; user: User; chats: Chat[]; glowOn: boolean; onClose: () => void; onOpenChat: (chatId: string) => void; onGlowToggle: (on: boolean) => void; onClearHistory: () => void; onToast: (message: string) => void; onExportData: () => Promise<void>; onDeleteAccount: (password?: string) => Promise<string | null>; }
type Tab = "general" | "appearance" | "security" | "billing" | "usage" | "agent-chats";
function formatTokens(value: number) { return value >= 1_000_000 ? `${(value / 1_000_000).toFixed(1)}M` : value >= 1_000 ? `${(value / 1_000).toFixed(1)}K` : String(value); }

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
  const [coachProgress, setCoachProgress] = useState<{ dashboard: DashboardData; history: Array<Record<string, any>> } | null>(null);
  const [coachProgressLoading, setCoachProgressLoading] = useState(false);
  const totalTokens = usage?.reduce((sum, item) => sum + (item.usage?.total_tokens ?? 0), 0) ?? 0; const totalRequests = usage?.reduce((sum, item) => sum + (item.usage?.total_requests ?? 0), 0) ?? 0;
  const monthlyLimit = 1_000_000;
  const usagePercent = Math.min(100, Math.round((totalTokens / monthlyLimit) * 100));
  const agentChatRows = AGENTS.map((agent) => {
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
      <aside className="settings-nav"><button className="settings-close" onClick={onClose}>×</button><h3>Settings</h3>{(["general", "appearance", "security", "billing", "usage", "agent-chats"] as Tab[]).map((item) => <button key={item} className={tab === item ? "active" : ""} onClick={() => setTab(item)}><span>{item === "general" ? "⚙" : item === "appearance" ? "◐" : item === "security" ? "⚿" : item === "billing" ? "▣" : item === "usage" ? "▤" : "◫"}</span>{item === "agent-chats" ? "Agent chats" : item[0].toUpperCase() + item.slice(1)}</button>)}</aside>
      <main className="settings-content">
        {tab === "general" && <><h2>General</h2><div className="settings-section"><div className="setting-row"><div><b>Profile</b><p>{user.name}<br />{user.email} · {user.mobile}</p></div></div><div className="setting-row"><div><b>Accent glow effects</b><p>Toggle animated glow on cards and buttons.</p></div><label className="switch"><input type="checkbox" checked={glowOn} onChange={(event) => onGlowToggle(event.target.checked)} /><span className="slider" /></label></div><div className="setting-row"><div><b>Clear chat history</b><p>Remove all saved conversations for this account.</p></div><button className="btn btn-outline btn-danger" onClick={() => setClearConfirmOpen(true)}>Clear</button></div></div>
          <h3 className="settings-title">Privacy &amp; data</h3>
          <p className="settings-subtitle">Your rights under the Digital Personal Data Protection Act, 2023.</p>
          <div className="settings-section">
            <div className="setting-row"><div><b>Download my data</b><p>Get a JSON copy of every piece of personal data DigiDARA holds about your account — the DPDP right to access.</p></div><button className="btn btn-outline" disabled={exporting} onClick={handleExport}>{exporting ? "Preparing…" : "Download"}</button></div>
            <div className="setting-row"><div><b>Delete my account</b><p>Permanently erase your account and personal data. This also withdraws your consent to processing and cannot be undone.</p></div><button className="btn btn-outline btn-danger" onClick={() => { setDeleteConfirmOpen(true); setDeleteError(""); setDeletePassword(""); }}>Delete account</button></div>
            <div className="setting-row"><div><b>Grievance Officer</b><p>Questions or complaints about how your data is handled: <a href="mailto:privacy@digidaraaiagents.com">privacy@digidaraaiagents.com</a>.</p></div></div>
          </div></>}
        {tab === "appearance" && <AppearanceSettings themePref={themePref} onThemeChange={onThemeChange} appearance={appearance} onAppearanceChange={onAppearanceChange} glowOn={glowOn} onGlowToggle={onGlowToggle} />}
        {tab === "security" && <SecuritySettings user={user} onToast={onToast} onLogout={onLogout} />}
        {tab === "billing" && <BillingPanel open={open} user={user} onToast={onToast} />}
        {tab === "usage" && <><h2>Usage</h2><p className="settings-subtitle">Track usage across your DigiDARA agents.</p><div className="settings-usage-summary"><div className="settings-platform-total"><span>Your usage</span><strong>{formatTokens(totalTokens)} tokens</strong><small>· {totalRequests} requests</small></div><div className="profile-usage-limit"><div><b>Monthly usage</b><span>{Math.max(0, 100 - usagePercent)}% remaining</span></div><div className="usage-progress"><span style={{ width: `${usagePercent}%` }} /></div><small>{formatTokens(totalTokens)} of {formatTokens(monthlyLimit)} tokens used</small></div></div><h3 className="settings-title">Agent usage</h3><div className="usage-settings-list">{usage?.map((item) => <div key={item.id}><span className="profile-agent-icon" style={{ background: item.color }}>{item.icon}</span><span><b>{item.label}</b><small>{item.usage ? `${formatTokens(item.usage.total_tokens)} tokens · ${item.usage.total_requests} requests` : "Not reachable"}</small></span><i className={item.online ? "" : "offline"} /></div>) ?? <p>Loading usage…</p>}</div></>}
        {tab === "agent-chats" && <><h2>Agent chats</h2><p className="settings-subtitle">Conversation activity and request history for every agent.</p><label className="agent-chat-search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></svg><input value={agentSearch} onChange={(event) => setAgentSearch(event.target.value)} placeholder="Search agents by name, category or capability…" /><span>{filteredAgentChatRows.length} agents</span>{agentSearch && <button onClick={() => setAgentSearch("")} aria-label="Clear search">×</button>}</label><div className="agent-chat-table">{filteredAgentChatRows.map(({ agent, chats: agentChats, requests, lastUsed }) => <article key={agent.id}><span className="agent-chat-icon" style={{ background: agent.color }}>{agent.icon}</span><div className="agent-chat-main"><b>{agent.name}</b><small>{agent.desc}</small></div><div className="agent-chat-metric"><b>{requests}</b><small>requests</small></div><div className="agent-chat-metric"><b>{agentChats.length}</b><small>chats</small></div><div className="agent-chat-last"><b>{lastUsed ? new Date(lastUsed).toLocaleDateString() : "Never"}</b><small>{lastUsed ? new Date(lastUsed).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "Not used"}</small></div><button onClick={() => setDetailAgentId(agent.id)}>More details</button></article>)}{filteredAgentChatRows.length === 0 && <div className="agent-chat-empty">No agents match “{agentSearch}”.</div>}</div></>}
      </main>
      {detailRow && <div className="agent-chat-detail"><div className="agent-chat-detail-head"><button onClick={() => setDetailAgentId(null)}>← Back</button><span>Agent details</span><button onClick={() => setDetailAgentId(null)}>×</button></div><div className="agent-chat-detail-body"><header><span className="agent-detail-mini-icon" style={{ background: detailRow.agent.color }}>{detailRow.agent.icon}</span><div><h2>{detailRow.agent.name}</h2><p>{detailRow.agent.desc}</p></div><span className={`agent-health${detailRow.usage?.online ? "" : " offline"}`}>{detailRow.usage?.online ? "Online" : "Offline"}</span></header><div className="agent-detail-cards"><article><span>Total chats</span><strong>{detailRow.chats.length}</strong><small>Saved conversations</small></article><article><span>Requests</span><strong>{detailRow.requests}</strong><small>Agent executions</small></article><article><span>Pending</span><strong>{detailRow.chats.filter((chat) => chat.messages.filter((message) => message.role === "user").length <= 1).length}</strong><small>Early-stage chats</small></article><article><span>Completed</span><strong>{detailRow.chats.filter((chat) => chat.messages.filter((message) => message.role === "user").length > 1).length}</strong><small>Multi-turn chats</small></article></div><section className="agent-detail-info"><h3>Activity information</h3><dl><div><dt>Last used</dt><dd>{detailRow.lastUsed ? new Date(detailRow.lastUsed).toLocaleString() : "Never used"}</dd></div><div><dt>Total messages</dt><dd>{detailRow.chats.reduce((sum, chat) => sum + chat.messages.length, 0)}</dd></div><div><dt>Tokens used</dt><dd>{formatTokens(detailRow.usage?.usage?.total_tokens ?? 0)}</dd></div><div><dt>Category</dt><dd>{detailRow.agent.category?.filter((item) => item !== "Top Picks").join(", ") || "General"}</dd></div><div><dt>Agent rating</dt><dd>★ {detailRow.agent.rating ?? "—"}</dd></div></dl></section>{detailRow.agent.id === "communication-coach" && <section className="coach-progress-detail"><h3>Progress & scores</h3>{coachProgressLoading ? <p>Loading progress…</p> : coachProgress ? <><div className="coach-score-grid"><article><span>Overall</span><strong>{coachProgress.dashboard.overall_score ?? "—"}/10</strong></article><article><span>Speaking</span><strong>{coachProgress.dashboard.speaking_average ?? "—"}/10</strong><small>{coachProgress.dashboard.speaking_completed} sessions</small></article><article><span>Writing</span><strong>{coachProgress.dashboard.writing_average ?? "—"}/10</strong><small>{coachProgress.dashboard.writing_completed} sessions</small></article><article><span>Pronunciation</span><strong>{coachProgress.dashboard.pronunciation_average ?? "—"}/10</strong><small>{coachProgress.dashboard.pronunciation_completed} sessions</small></article></div><div className="coach-history-list"><h3>Practice history</h3>{coachProgress.history.length ? coachProgress.history.slice(0, 8).map((item, index) => <div key={`${item.type ?? "session"}-${item.session_id ?? index}`}><span><b>{item.topic_title ?? item.title ?? "Practice session"}</b><small>{item.type ?? "Practice"}{item.completed_at ? ` · ${new Date(item.completed_at).toLocaleString()}` : ""}</small></span><strong>{item.overall_score ?? "—"}/10</strong></div>) : <p>No completed practice sessions yet.</p>}</div></> : <p>Progress is unavailable right now.</p>}</section>}<section className="recent-agent-chats"><h3>Recent chats</h3>{detailRow.chats.length ? detailRow.chats.slice(0, 8).map((chat) => { const userTurns = chat.messages.filter((message) => message.role === "user").length; return <button key={chat.id} onClick={() => onOpenChat(chat.id)}><span><b>{chat.title}</b><small>{chat.messages.length} messages · {new Date(chat.updatedAt).toLocaleString()}</small></span><i className={userTurns > 1 ? "completed" : "pending"}>{userTurns > 1 ? "Completed" : "Pending"}</i><em>›</em></button>; }) : <p>No conversations with this agent yet.</p>}</section></div></div>}
    </div>
    {clearConfirmOpen && <ConfirmDialog title="Clear all chat history?" message="Every saved conversation for this account will be deleted. This cannot be undone." confirmLabel="Clear all" onCancel={() => setClearConfirmOpen(false)} onConfirm={() => { setClearConfirmOpen(false); onClearHistory(); }} />}
    {deleteConfirmOpen && <div className="modal-overlay open" onClick={(event) => event.target === event.currentTarget && !deleting && setDeleteConfirmOpen(false)}>
      <div className="modal-card" style={{ maxWidth: 420 }}>
        <div className="modal-head"><h3>Delete your account?</h3><button type="button" className="icon-btn" aria-label="Close" onClick={() => setDeleteConfirmOpen(false)}>✕</button></div>
        <div className="modal-body">
          <p>This permanently erases your DigiDARA account and personal data — name, email, mobile, and consent record — and withdraws your consent to processing. It cannot be undone.</p>
          <label className="field"><span>Confirm your password</span><input type="password" placeholder="Leave blank if you only sign in with Google" value={deletePassword} onChange={(event) => setDeletePassword(event.target.value)} /></label>
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
