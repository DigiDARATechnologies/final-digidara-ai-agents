import { useState } from "react";
import { downloadPaymentsCsv, fetchPayments, type PaymentMethodFilter, type PaymentTotal } from "../../lib/adminApi";
import { formatDate, formatMoney, formatNumber, PAYMENT_BADGE } from "./adminFormat";
import { formatPoints } from "../../lib/points";
import { useLoad } from "./useLoad";

const PAGE = 25;

export default function PaymentsPanel() {
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [method, setMethod] = useState<PaymentMethodFilter>("");
  const [page, setPage] = useState(1);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const { data, error, loading, reload } = useLoad(() => fetchPayments({ status, search: query, method, page, limit: PAGE }), [status, query, method, page]);

  async function exportCsv() {
    setExporting(true);
    setExportError("");
    try {
      await downloadPaymentsCsv({ status, search: query, method });
    } catch (err) {
      setExportError((err as Error).message);
    } finally {
      setExporting(false);
    }
  }

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE)) : 1;
  // "Paid" becomes two cards: money that came through Razorpay and money recorded by hand.
  // Manual rows are mostly recorded at ₹0, so their card shows what they are worth at plan prices.
  const kpis = Object.entries(data?.summary ?? {}).flatMap(([name, row]): [string, PaymentTotal, string?][] =>
    name === "paid" && data?.paid_by_method
      ? [
          ["Paid · Razorpay", data.paid_by_method.razorpay],
          ["Paid · Manual", { count: data.paid_by_method.manual.count, amount: data.paid_by_method.manual.value ?? data.paid_by_method.manual.amount },
            `at plan prices · ${formatMoney(data.paid_by_method.manual.amount)} recorded`],
        ]
      : [[name, row]]);
  return (
    <div className="admin-section">
      <div className="admin-kpis">
        {kpis.map(([name, row, note]) => (
          <div className="admin-kpi" key={name}><span>{name}</span><strong>{formatMoney(row.amount)}</strong>
            <small>{formatNumber(row.count)} payment{row.count === 1 ? "" : "s"}{note ? ` · ${note}` : ""}</small></div>
        ))}
      </div>
      <form className="admin-toolbar" onSubmit={(event) => { event.preventDefault(); setPage(1); setQuery(search.trim()); }}>
        <input className="admin-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search by email, name or Razorpay id" aria-label="Search payments" />
        <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }} aria-label="Filter by status">
          <option value="">All statuses</option><option value="paid">Paid</option><option value="created">Awaiting payment</option><option value="failed">Failed</option>
        </select>
        <select value={method} onChange={(event) => { setMethod(event.target.value as PaymentMethodFilter); setPage(1); }} aria-label="Filter by payment type">
          <option value="">All types</option><option value="razorpay">Razorpay</option><option value="manual">Manual</option>
        </select>
        <button className="btn btn-outline btn-sm" type="submit">Search</button>
        <button className="btn btn-primary btn-sm" type="button" disabled={exporting} onClick={() => void exportCsv()}>
          {exporting ? "Exporting…" : "Export CSV"}
        </button>
      </form>
      {exportError && <div className="admin-error">{exportError}</div>}
      {error && <div className="admin-error">{error} <button className="btn btn-outline btn-sm" onClick={reload}>Retry</button></div>}
      <div className="admin-table-card">
        <table className="admin-table">
          <thead><tr><th>User</th><th>For</th><th>Amount</th><th>Coins</th><th>Status</th><th>Created</th><th>Paid</th><th>Type / Razorpay</th></tr></thead>
          <tbody>
            {data?.payments.map((p) => (
              <tr key={p.id}>
                <td className="admin-table-primary">{p.email}<br /><small>{p.name}</small></td>
                <td>{p.label}</td>
                <td>{formatMoney(p.amount)}{p.method === "manual" && !p.amount && p.value ? <><br /><small>Plan price {formatMoney(p.value)}</small></> : null}</td><td>{p.points ? formatPoints(p.points) : "—"}</td>
                <td><span className={`admin-badge ${PAYMENT_BADGE[p.status] || "badge-expired"}`}>{p.status}</span></td>
                <td>{formatDate(p.created_at)}</td><td>{formatDate(p.paid_at)}</td>
                <td><small>{p.method === "manual" ? <b>Manual</b> : p.razorpay_payment_id || "—"}<br />{p.razorpay_order_id}</small></td>
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
