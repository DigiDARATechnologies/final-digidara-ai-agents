import { fetchOverview } from "../../lib/adminApi";
import { agentLabel, formatDate, formatMoney, formatNumber, PAYMENT_BADGE } from "./adminFormat";
import { useLoad } from "./useLoad";

function Kpi({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="admin-kpi">
      <span>{label}</span>
      <strong>{value}</strong>
      {note && <small>{note}</small>}
    </div>
  );
}

export default function DashboardPanel() {
  const { data, error, loading, reload } = useLoad(fetchOverview, []);
  if (loading && !data) return <p className="admin-loading">Loading the dashboard…</p>;
  if (error) return <div className="admin-error">{error} <button className="btn btn-outline btn-sm" onClick={reload}>Retry</button></div>;
  if (!data) return null;

  const { users, revenue, tokens, activity, agents } = data;
  const peak = Math.max(1, ...revenue.daily.map((day) => day.amount));
  return (
    <div className="admin-section">
      <div className="admin-toolbar">
        <small className="admin-loading">Updated {formatDate(data.generated_at)}</small>
        <button className="btn btn-outline btn-sm" onClick={reload} disabled={loading}>{loading ? "Refreshing…" : "Refresh"}</button>
      </div>

      <h4>Money</h4>
      <div className="admin-kpis">
        <Kpi label="Total revenue" value={formatMoney(revenue.total)} note={`${revenue.paid_count} paid payments`} />
        <Kpi label="Last 30 days" value={formatMoney(revenue.last_30d)} note={`${formatMoney(revenue.last_7d)} in the last 7 days`} />
        <Kpi label="Paying customers" value={formatNumber(revenue.paying_customers)} note={`${formatNumber(users.total)} users in all`} />
        <Kpi label="Awaiting payment" value={formatNumber(revenue.by_status.created ?? 0)} note={`${formatNumber(revenue.by_status.failed ?? 0)} failed`} />
      </div>

      <h4>Users and tokens</h4>
      <div className="admin-kpis">
        <Kpi label="Users" value={formatNumber(users.total)} note={`${users.new_7d} new this week · ${users.new_30d} this month`} />
        <Kpi label="Active this week" value={formatNumber(activity.active_users_7d)} note={`${formatNumber(activity.conversations)} chats · ${formatNumber(activity.messages)} messages`} />
        <Kpi label="Tokens sold" value={formatNumber(tokens.credited_by_payments)} note="credited by payments" />
        <Kpi label="Tokens left with users" value={formatNumber(tokens.outstanding_balance)} note={`${tokens.users_out_of_tokens} user${tokens.users_out_of_tokens === 1 ? "" : "s"} out of tokens`} />
        <Kpi label="Agents online" value={`${agents.healthy} / ${agents.registered}`} note="by heartbeat" />
      </div>

      <h4>Revenue, last 30 days</h4>
      <div className="admin-chart" role="img" aria-label="Daily revenue for the last 30 days">
        {revenue.daily.map((day) => (
          <div className="admin-chart-col" key={day.date} title={`${day.date}: ${formatMoney(day.amount)} (${day.count} payment${day.count === 1 ? "" : "s"})`}>
            <span style={{ height: `${Math.max(2, (day.amount / peak) * 100)}%` }} className={day.amount ? "has-value" : ""} />
          </div>
        ))}
      </div>

      <div className="admin-two-col">
        <div>
          <h4>Revenue by plan</h4>
          <div className="admin-table-card">
            <table className="admin-table">
              <thead><tr><th>Plan</th><th>Payments</th><th>Amount</th></tr></thead>
              <tbody>
                {revenue.by_plan.map((plan) => <tr key={plan.plan_id}><td className="admin-table-primary">{plan.label}</td><td>{plan.count}</td><td>{formatMoney(plan.amount)}</td></tr>)}
                {!revenue.by_plan.length && <tr><td colSpan={3} className="admin-table-empty">No paid payments yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
        <div>
          <h4>Usage by agent</h4>
          <div className="admin-table-card">
            <table className="admin-table">
              <thead><tr><th>Agent</th><th>Chats</th><th>Users</th><th>Messages</th></tr></thead>
              <tbody>
                {activity.by_agent.map((row) => <tr key={row.agent_id}><td className="admin-table-primary">{agentLabel(row.agent_id)}</td><td>{row.chats}</td><td>{row.users}</td><td>{row.messages}</td></tr>)}
                {!activity.by_agent.length && <tr><td colSpan={4} className="admin-table-empty">No chats yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="admin-two-col">
        <div>
          <h4>Newest users</h4>
          <div className="admin-table-card">
            <table className="admin-table">
              <thead><tr><th>Name</th><th>Email</th><th>Joined</th></tr></thead>
              <tbody>{data.recent_signups.map((u) => <tr key={u.id}><td className="admin-table-primary">{u.name}</td><td>{u.email}</td><td>{formatDate(u.created_at)}</td></tr>)}</tbody>
            </table>
          </div>
        </div>
        <div>
          <h4>Latest payments</h4>
          <div className="admin-table-card">
            <table className="admin-table">
              <thead><tr><th>User</th><th>For</th><th>Amount</th><th>Status</th></tr></thead>
              <tbody>
                {data.recent_payments.map((p) => (
                  <tr key={p.id}><td className="admin-table-primary">{p.email}</td><td>{p.label}</td><td>{formatMoney(p.amount)}</td><td><span className={`admin-badge ${PAYMENT_BADGE[p.status] || "badge-expired"}`}>{p.status}</span></td></tr>
                ))}
                {!data.recent_payments.length && <tr><td colSpan={4} className="admin-table-empty">No payments yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
