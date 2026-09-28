import { useState } from "react";
import { fetchConversation, fetchUserDetail, fetchUsers } from "../../lib/adminApi";
import { agentLabel, formatDate, formatMoney, formatNumber, PAYMENT_BADGE } from "./adminFormat";
import { useLoad } from "./useLoad";

const PAGE = 25;

function Conversation({ userId, conversationId, onClose }: { userId: string; conversationId: string; onClose: () => void }) {
  const { data, error, loading } = useLoad(() => fetchConversation(userId, conversationId), [userId, conversationId]);
  return (
    <div className="admin-conversation">
      <div className="admin-toolbar">
        <strong>{data ? `${agentLabel(data.agent_id)} · ${data.title}` : "Conversation"}</strong>
        <button className="btn btn-outline btn-sm" onClick={onClose}>Close</button>
      </div>
      {loading && <p className="admin-loading">Loading messages…</p>}
      {error && <div className="admin-error">{error}</div>}
      {data?.messages.map((message, index) => (
        <div className={`admin-message ${message.role === "user" ? "from-user" : "from-agent"}`} key={index}>
          <small>{message.role === "user" ? "User" : "Agent"} · {message.time}</small>
          <p>{message.content}</p>
        </div>
      ))}
      {data && !data.messages.length && <p className="admin-loading">No messages saved in this conversation.</p>}
    </div>
  );
}

function UserDetail({ userId, onBack }: { userId: string; onBack: () => void }) {
  const { data, error, loading } = useLoad(() => fetchUserDetail(userId), [userId]);
  const [open, setOpen] = useState<string | null>(null);
  if (loading && !data) return <p className="admin-loading">Loading this user…</p>;
  if (error) return <div className="admin-section"><button className="btn btn-outline btn-sm admin-back-btn" onClick={onBack}>← All users</button><div className="admin-error">{error}</div></div>;
  if (!data) return null;
  const { user, totals } = data;
  return (
    <div className="admin-section">
      <button className="btn btn-outline btn-sm admin-back-btn" onClick={onBack}>← All users</button>
      <div className="admin-user-head">
        <div>
          <h3>{user.name}{user.is_admin && <span className="admin-badge badge-pending">admin</span>}</h3>
          <p>{user.email}{user.mobile ? ` · ${user.mobile}` : ""} · {user.google ? "Google sign-in" : "Email and password"}</p>
          <small>Joined {formatDate(user.created_at)}{user.consent_accepted_at ? ` · consent ${formatDate(user.consent_accepted_at)} (policy ${user.consent_policy_version ?? "?"})` : ""}</small>
        </div>
      </div>
      <div className="admin-kpis">
        <div className="admin-kpi"><span>Paid so far</span><strong>{formatMoney(totals.paid)}</strong><small>{totals.paid_payments} of {totals.payments} payments paid</small></div>
        <div className="admin-kpi"><span>Token balance</span><strong>{formatNumber(user.token_balance)}</strong><small>{formatNumber(totals.tokens_bought)} bought</small></div>
        <div className="admin-kpi"><span>Chats</span><strong>{formatNumber(totals.conversations)}</strong><small>{formatNumber(totals.messages)} messages</small></div>
      </div>

      <h4>Payments</h4>
      <div className="admin-table-card">
        <table className="admin-table">
          <thead><tr><th>For</th><th>Amount</th><th>Tokens</th><th>Status</th><th>Created</th><th>Paid</th><th>Razorpay</th></tr></thead>
          <tbody>
            {data.payments.map((p) => (
              <tr key={p.id}>
                <td className="admin-table-primary">{p.label}</td><td>{formatMoney(p.amount)}</td><td>{p.tokens ? formatNumber(p.tokens) : "—"}</td>
                <td><span className={`admin-badge ${PAYMENT_BADGE[p.status] || "badge-expired"}`}>{p.status}</span></td>
                <td>{formatDate(p.created_at)}</td><td>{formatDate(p.paid_at)}</td><td><small>{p.razorpay_payment_id || "—"}</small></td>
              </tr>
            ))}
            {!data.payments.length && <tr><td colSpan={7} className="admin-table-empty">No payments.</td></tr>}
          </tbody>
        </table>
      </div>

      <h4>Chats with agents</h4>
      <div className="admin-table-card">
        <table className="admin-table">
          <thead><tr><th>Agent</th><th>Title</th><th>Messages</th><th>Last activity</th><th /></tr></thead>
          <tbody>
            {data.conversations.map((c) => (
              <tr key={c.id}>
                <td className="admin-table-primary">{agentLabel(c.agent_id)}</td>
                <td>{c.title}{c.deleted && <span className="admin-badge badge-expired">deleted by user</span>}</td>
                <td>{c.messages}</td><td>{formatDate(c.updated_at)}</td>
                <td><button className="btn btn-outline btn-sm" onClick={() => setOpen(open === c.id ? null : c.id)}>{open === c.id ? "Hide" : "Read"}</button></td>
              </tr>
            ))}
            {!data.conversations.length && <tr><td colSpan={5} className="admin-table-empty">No chats yet.</td></tr>}
          </tbody>
        </table>
      </div>
      {open && <Conversation userId={userId} conversationId={open} onClose={() => setOpen(null)} />}

      <h4>Where they are in each agent</h4>
      <div className="admin-table-card">
        <table className="admin-table">
          <thead><tr><th>Agent</th><th>Current step</th><th>Updated</th></tr></thead>
          <tbody>
            {data.agent_progress.map((p) => (
              <tr key={`${p.agent_id}:${p.chat_id}`}><td className="admin-table-primary">{p.agent_id}</td><td>{p.step ? p.step.replace(/_/g, " ") : "—"}</td><td>{formatDate(p.updated_at)}</td></tr>
            ))}
            {!data.agent_progress.length && <tr><td colSpan={3} className="admin-table-empty">No saved agent progress.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function UsersPanel() {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const { data, error, loading, reload } = useLoad(() => fetchUsers({ search: query, sort, page, limit: PAGE }), [query, sort, page]);

  if (selected) return <UserDetail userId={selected} onBack={() => setSelected(null)} />;
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE)) : 1;
  return (
    <div className="admin-section">
      <form className="admin-toolbar" onSubmit={(event) => { event.preventDefault(); setPage(1); setQuery(search.trim()); }}>
        <input className="admin-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search by name, email or mobile" aria-label="Search users" />
        <select value={sort} onChange={(event) => { setSort(event.target.value); setPage(1); }} aria-label="Sort users">
          <option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="spent">Most paid</option>
          <option value="active">Recently active</option><option value="balance">Lowest tokens</option>
        </select>
        <button className="btn btn-outline btn-sm" type="submit">Search</button>
      </form>
      {error && <div className="admin-error">{error} <button className="btn btn-outline btn-sm" onClick={reload}>Retry</button></div>}
      <div className="admin-table-card">
        <table className="admin-table">
          <thead><tr><th>User</th><th>Joined</th><th>Tokens</th><th>Paid</th><th>Chats</th><th>Agents used</th><th>Last active</th></tr></thead>
          <tbody>
            {data?.users.map((u) => (
              <tr key={u.id} className="admin-row-click" onClick={() => setSelected(u.id)} tabIndex={0}
                onKeyDown={(event) => { if (event.key === "Enter") setSelected(u.id); }}>
                <td className="admin-table-primary">{u.name}{u.is_admin && <span className="admin-badge badge-pending">admin</span>}<br /><small>{u.email}</small></td>
                <td>{formatDate(u.created_at)}</td><td>{formatNumber(u.token_balance)}</td><td>{formatMoney(u.paid_total)}</td>
                <td>{u.chats}</td><td>{u.agents_used}</td><td>{formatDate(u.last_active)}</td>
              </tr>
            ))}
            {data && !data.users.length && <tr><td colSpan={7} className="admin-table-empty">No users match.</td></tr>}
            {loading && !data && <tr><td colSpan={7} className="admin-table-empty">Loading…</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="admin-toolbar">
        <button className="btn btn-outline btn-sm" disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>← Previous</button>
        <small className="admin-loading">Page {page} of {pages} · {data ? formatNumber(data.total) : 0} users · click a user for their full history</small>
        <button className="btn btn-outline btn-sm" disabled={page >= pages || loading} onClick={() => setPage(page + 1)}>Next →</button>
      </div>
    </div>
  );
}
