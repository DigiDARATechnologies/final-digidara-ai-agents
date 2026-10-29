import { useCallback, useEffect, useRef, useState } from "react";
import {
  decideJoinRequest,
  downloadRosterTemplate,
  fetchJoinRequests,
  fetchRoster,
  removeRosterEntry,
  uploadRoster,
  type JoinRequest,
  type RosterEntry,
  type RosterUploadResult,
  type StaffLogin,
} from "../../lib/orgApi";

const STATUS_TEXT: Record<RosterEntry["status"], string> = {
  joined: "Joined",
  waiting: "Has an account, not joined yet",
  not_signed_up: "Not signed up yet",
  other_organization: "In another organization",
};

function when(iso: string | null): string {
  return iso ? new Date(iso.endsWith("Z") ? iso : `${iso}Z`).toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : "—";
}

/** Staff upload the organization's student list (Excel or CSV: name, mobile,
 * email). Listed students join on their own once they sign in; anyone else
 * who uses a join code waits here for approval. */
export default function StudentListPanel({ orgId, orgName, staff = [], onChanged, onToast }: {
  orgId: string; orgName: string; staff?: StaffLogin[]; onChanged: () => void; onToast: (message: string) => void;
}) {
  const [staffFilter, setStaffFilter] = useState("");
  const [entries, setEntries] = useState<RosterEntry[] | null>(null);
  const [requests, setRequests] = useState<JoinRequest[]>([]);
  const [result, setResult] = useState<RosterUploadResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const input = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const [list, waiting] = await Promise.all([fetchRoster(orgId), fetchJoinRequests(orgId)]);
      setEntries(list);
      setRequests(waiting);
      setError("");
    } catch (err) {
      setError((err as Error).message);
    }
  }, [orgId]);

  useEffect(() => { void load(); }, [load]);

  async function upload(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const done = await uploadRoster(orgId, file);
      setResult(done);
      onToast(`${done.added} added, ${done.updated} updated${done.joined + done.approved ? `, ${done.joined + done.approved} joined now` : ""}.`);
      await load();
      onChanged();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  async function decide(request: JoinRequest, approve: boolean) {
    try {
      await decideJoinRequest(orgId, request.id, approve);
      onToast(approve ? `${request.name} joined ${orgName}.` : `${request.name}'s request was declined.`);
      await load();
      if (approve) onChanged();
    } catch (err) {
      onToast((err as Error).message);
    }
  }

  async function remove(entry: RosterEntry) {
    if (!window.confirm(`Take ${entry.email} off the list? ${entry.status === "joined" ? "They stay in the organization." : ""}`)) return;
    try {
      await removeRosterEntry(orgId, entry.id);
      await load();
    } catch (err) {
      onToast((err as Error).message);
    }
  }

  const term = search.trim().toLowerCase();
  const staffName = (e: RosterEntry) => staff.find((s) => s.user_id === e.uploaded_by)?.name ?? "";
  const shown = (entries ?? []).filter((e) => (!term || `${e.name} ${e.email} ${e.mobile}`.toLowerCase().includes(term))
    && (!staffFilter || (staffFilter === "none" ? !staffName(e) : e.uploaded_by === staffFilter)));

  return (
    <div className="org-grid-1">
      {requests.length > 0 && (
        <section className="org-card">
          <div className="org-card-head"><h3>Waiting for approval ({requests.length})</h3>
            <span className="rd-muted">Used a join code but not on the student list</span></div>
          <div className="org-table-wrap">
            <table className="org-table compact">
              <thead><tr><th>Learner</th><th>Class</th><th>Code</th><th>Asked</th><th /></tr></thead>
              <tbody>
                {requests.map((r) => (
                  <tr key={r.id}>
                    <td><b>{r.name}</b><br /><small>{r.email}</small></td>
                    <td>{[r.department, r.year, r.section].filter(Boolean).join(" · ") || "—"}</td>
                    <td>{r.join_code ?? "—"}</td>
                    <td>{when(r.requested_at)}</td>
                    <td className="org-actions">
                      <button type="button" className="btn btn-primary btn-sm" onClick={() => void decide(r, true)}>Approve</button>
                      <button type="button" className="btn btn-outline btn-sm" onClick={() => void decide(r, false)}>Decline</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="org-card">
        <h3>Upload the student list</h3>
        <p className="rd-muted">
          An Excel (.xlsx) or CSV file with <b>Name</b>, <b>Mobile</b> and <b>Email</b> columns (download the template to see the
          format). Share your join code with these students: when one signs in with an email on your list and enters your code, they
          join {orgName} at once. Anyone else who uses your code waits for your approval. Uploading again adds new students and
          updates names and mobiles.
        </p>
        <div className="org-actions">
          <input ref={input} type="file" hidden accept=".xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
            onChange={(e) => void upload(e.target.files?.[0])} />
          <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={() => input.current?.click()}>
            {busy ? "Uploading…" : "Choose file"}
          </button>
          <button type="button" className="btn btn-outline btn-sm"
            onClick={() => void downloadRosterTemplate(orgId).catch((err) => onToast((err as Error).message))}>
            Download template
          </button>
          <span className="rd-muted">Up to 5,000 students, 5 MB.</span>
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
        {result && (
          <p className="rd-muted">
            {result.added} added · {result.updated} updated · {result.joined + result.approved} joined now
            {result.invalid_count > 0 && <> · <b>{result.invalid_count} skipped</b> (rows {result.invalid.slice(0, 10).map((r) => r.row).join(", ")}
              {result.invalid_count > 10 ? "…" : ""}: not a valid email)</>}
          </p>
        )}
      </section>

      <section className="org-card">
        <div className="org-card-head">
          <h3>Student list ({staffFilter ? `${shown.length} of ` : ""}{entries?.length ?? 0})</h3>
          <div className="org-actions">
            {staff.length > 0 && (
              <select className="og-search" value={staffFilter} aria-label="Uploaded by staff" onChange={(e) => setStaffFilter(e.target.value)}>
                <option value="">All staff</option>
                {staff.map((s) => <option key={s.user_id} value={s.user_id}>{s.name}</option>)}
                <option value="none">Uploaded by owner or admin</option>
              </select>
            )}
            <input className="og-search" value={search} placeholder="Search name, email or mobile" onChange={(e) => setSearch(e.target.value)} />
          </div>
        </div>
        {entries === null ? <div className="org-skeleton" /> : (
          <div className="org-table-wrap">
            <table className="org-table compact">
              <thead><tr><th>Name</th><th>Email</th><th>Mobile</th>{staff.length > 0 && <th>Staff</th>}<th>Status</th><th /></tr></thead>
              <tbody>
                {shown.slice(0, 500).map((e) => (
                  <tr key={e.id}>
                    <td>{e.name || "—"}</td><td>{e.email}</td><td>{e.mobile || "—"}</td>
                    {staff.length > 0 && <td>{staffName(e) || <span className="rd-muted">—</span>}</td>}
                    <td><span className={`org-chip status-${e.status}`}>{STATUS_TEXT[e.status]}</span></td>
                    <td><button type="button" className="link-btn" onClick={() => void remove(e)}>Remove</button></td>
                  </tr>
                ))}
                {shown.length === 0 && <tr><td colSpan={staff.length > 0 ? 6 : 5} className="org-empty">{entries.length ? "No student matches." : "No list uploaded yet."}</td></tr>}
              </tbody>
            </table>
            {shown.length > 500 && <p className="rd-muted">Showing the first 500. Search to find others.</p>}
          </div>
        )}
      </section>
    </div>
  );
}
