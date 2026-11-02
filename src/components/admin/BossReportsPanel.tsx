import { fetchBossReports } from "../../lib/adminApi";
import { formatDate } from "./adminFormat";
import { useLoad } from "./useLoad";

const CATEGORIES: Record<string, string> = {
  interview: "Interview", score: "Score", level: "Level", link: "Link", other: "Other",
};

/** Problems learners asked Boss to report. The first table counts each kind over
 * the last 30 days, so a problem that keeps coming back stands out. */
export default function BossReportsPanel() {
  const { data, error, loading, reload } = useLoad(() => fetchBossReports(), []);
  return (
    <div className="admin-section">
      {error && <div className="admin-error">{error} <button className="btn btn-outline btn-sm" onClick={reload}>Retry</button></div>}
      <div className="admin-table-card">
        <table className="admin-table">
          <thead><tr><th>Kind of problem</th><th>Reports (30 days)</th><th>Learners</th></tr></thead>
          <tbody>
            {data?.repeated.map((row) => (
              <tr key={row.category}>
                <td className="admin-table-primary">{CATEGORIES[row.category] ?? row.category}</td>
                <td>{row.reports}</td>
                <td>{row.learners}</td>
              </tr>
            ))}
            {data && !data.repeated.length && <tr><td colSpan={3} className="admin-table-empty">No reports in the last 30 days.</td></tr>}
            {loading && !data && <tr><td colSpan={3} className="admin-table-empty">Loading…</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="admin-table-card">
        <table className="admin-table">
          <thead><tr><th>Learner</th><th>Kind</th><th>Agent</th><th>What they said</th><th>Received</th></tr></thead>
          <tbody>
            {data?.reports.map((row) => (
              <tr key={row.id}>
                <td className="admin-table-primary">{row.name}<br /><small>{row.email}</small></td>
                <td>{CATEGORIES[row.category] ?? row.category}</td>
                <td>{row.agent_id || "—"}</td>
                <td style={{ maxWidth: 360, whiteSpace: "pre-wrap" }}>{row.message || "—"}</td>
                <td>{formatDate(row.created_at)}</td>
              </tr>
            ))}
            {data && !data.reports.length && <tr><td colSpan={5} className="admin-table-empty">No reports yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
