import { fetchEnterpriseEnquiries } from "../../lib/adminApi";
import { formatDate } from "./adminFormat";
import { useLoad } from "./useLoad";

const TYPES: Record<string, string> = {
  college: "College / university", training_institute: "Training institute", company: "Company", other: "Other",
};

/** Enterprise plan enquiries: who asked, how to reach them, and whether the
 * email to support went out. Reply opens the mail app addressed to them. */
export default function EnterprisePanel() {
  const { data, error, loading, reload } = useLoad(() => fetchEnterpriseEnquiries(), []);
  return (
    <div className="admin-section">
      {error && <div className="admin-error">{error} <button className="btn btn-outline btn-sm" onClick={reload}>Retry</button></div>}
      <div className="admin-table-card">
        <table className="admin-table">
          <thead><tr><th>Organization</th><th>Contact</th><th>Learners</th><th>Message</th><th>Received</th><th>Email</th><th /></tr></thead>
          <tbody>
            {data?.enquiries.map((e) => (
              <tr key={e.id}>
                <td className="admin-table-primary">{e.organization}<br /><small>{TYPES[e.organization_type] ?? e.organization_type}{e.city ? ` · ${e.city}` : ""}</small></td>
                <td>{e.contact_name}<br /><small>{e.email}<br />{e.phone}</small></td>
                <td>{e.learners ?? "—"}</td>
                <td style={{ maxWidth: 320, whiteSpace: "pre-wrap" }}>{e.message || "—"}</td>
                <td>{formatDate(e.created_at)}</td>
                <td><span className={`admin-badge ${e.emailed ? "badge-active" : "badge-rejected"}`}>{e.emailed ? "Sent" : "Not sent"}</span></td>
                <td><a className="btn btn-outline btn-sm" href={`mailto:${e.email}?subject=${encodeURIComponent(`SkillDARA Enterprise for ${e.organization}`)}`}>Reply</a></td>
              </tr>
            ))}
            {data && !data.enquiries.length && <tr><td colSpan={7} className="admin-table-empty">No enquiries yet.</td></tr>}
            {loading && !data && <tr><td colSpan={7} className="admin-table-empty">Loading…</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
