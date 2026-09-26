import { useState } from "react";
import { fetchPayments } from "../../lib/adminApi";
import { formatDate, formatMoney, formatNumber, PAYMENT_BADGE } from "./adminFormat";
import { useLoad } from "./useLoad";

const PAGE = 25;

export default function PaymentsPanel() {
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useLoad(() => fetchPayments({ status, search: query, page, limit: PAGE }), [status, query, page]);

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE)) : 1;
  return (
    <div className="admin-section">
      <div className="admin-kpis">
        {Object.entries(data?.summary ?? {}).map(([name, row]) => (
          <div className="admin-kpi" key={name}><span>{name}</span><strong>{formatMoney(row.amount)}</strong><small>{formatNumber(row.count)} payment{row.count === 1 ? "" : "s"}</small></div>
        ))}
      </div>
      <form className="admin-toolbar" onSubmit={(event) => { event.preventDefault(); setPage(1); setQuery(search.trim()); }}>
        <input className="admin-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search by email, name or Razorpay id" aria-label="Search payments" />
        <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }} aria-label="Filter by status">
          <option value="">All statuses</option><option value="paid">Paid</option><option value="created">Awaiting payment</option><option value="failed">Failed</option>
        </select>
        <button className="btn btn-outline btn-sm" type="submit">Search</button>
      </form>
      {error && <div className="admin-error">{error} <button className="btn btn-outline btn-sm" onClick={reload}>Retry</button></div>}
      <div className="admin-table-card">
        <table className="admin-table">
          <thead><tr><th>User</th><th>For</th><th>Amount</th><th>Tokens</th><th>Status</th><th>Created</th><th>Paid</th><th>Razorpay</th></tr></thead>
          <tbody>
            {data?.payments.map((p) => (
              <tr key={p.id}>
                <td className="admin-table-primary">{p.email}<br /><small>{p.name}</small></td>
                <td>{p.label}</td><td>{formatMoney(p.amount)}</td><td>{p.tokens ? formatNumber(p.tokens) : "—"}</td>
                <td><span className={`admin-badge ${PAYMENT_BADGE[p.status] || "badge-expired"}`}>{p.status}</span></td>
                <td>{formatDate(p.created_at)}</td><td>{formatDate(p.paid_at)}</td>
                <td><small>{p.razorpay_payment_id || "—"}<br />{p.razorpay_order_id}</small></td>
              </tr>
            ))}
            {data && !data.payments.length && <tr><td colSpan={8} className="admin-table-empty">No payments match.</td></tr>}
            {loading && !data && <tr><td colSpan={8} className="admin-table-empty">Loading…</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="admin-toolbar">
        <button className="btn btn-outline btn-sm" disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>← Previous</button>
        <small className="admin-loading">Page {page} of {pages} · {data ? formatNumber(data.total) : 0} payments</small>
        <button className="btn btn-outline btn-sm" disabled={page >= pages || loading} onClick={() => setPage(page + 1)}>Next →</button>
      </div>
    </div>
  );
}
