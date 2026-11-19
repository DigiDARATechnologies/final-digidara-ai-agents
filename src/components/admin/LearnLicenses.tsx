import { useEffect, useState } from "react";
import { fetchLicenses, setLicense, type LicenseRow } from "../../lib/learnApi";

/** Which colleges may read the Learning Hub without spending coins. */
export default function LearnLicenses() {
  const [rows, setRows] = useState<LicenseRow[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    fetchLicenses().then(setRows).catch((err) => setError((err as Error).message));
  }, []);

  async function toggle(row: LicenseRow) {
    setBusy(row.organization_id); setError("");
    try {
      const result = await setLicense(row.organization_id, !row.licensed);
      setRows((current) => current && current.map((r) => (r.organization_id === row.organization_id ? { ...r, licensed: result.licensed } : r)));
    } catch (err) { setError((err as Error).message); }
    setBusy("");
  }

  return (
    <section className="crs-card" aria-label="Learning Hub licences">
      <h3>Learning Hub: college licences</h3>
      <p className="crs-muted">Members of a licensed college read the Learning Hub without spending coins. Everyone else needs paid coins.</p>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="admin-table-card">
        <table className="admin-table">
          <thead><tr><th>Organization</th><th>Type</th><th>Licence</th><th /></tr></thead>
          <tbody>
            {rows?.map((row) => (
              <tr key={row.organization_id}>
                <td className="admin-table-primary">{row.name}</td>
                <td>{row.kind}</td>
                <td><span className={`admin-badge ${row.licensed ? "badge-active" : "badge-expired"}`}>{row.licensed ? "Licensed" : "No licence"}</span></td>
                <td>
                  <button type="button" className="btn btn-outline btn-sm" disabled={busy === row.organization_id} onClick={() => void toggle(row)}>
                    {row.licensed ? "Remove licence" : "Give licence"}
                  </button>
                </td>
              </tr>
            ))}
            {rows && !rows.length && <tr><td colSpan={4} className="admin-table-empty">No organizations yet.</td></tr>}
            {!rows && !error && <tr><td colSpan={4} className="admin-table-empty">Loading…</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}
