import { useState } from "react";
import { fetchBossReports, messageBossReporter, setBossReportStatus, type BossReportRow } from "../../lib/adminApi";
import { agentLabel, formatDate } from "./adminFormat";
import { useLoad } from "./useLoad";

const CATEGORIES: Record<string, string> = {
  interview: "Interview", score: "Score", level: "Level", link: "Link", other: "Other",
};
const SOLVED_TEXT = "Good news: the problem you reported to Boss has been solved. Thank you for telling us!";

/** The team's reply box under one report: "solve" marks it solved and sends
 * the note; "message" just sends it. The learner sees it in a popup the next
 * time they open SkillDARA. */
function ReplyBox({ row, mode, onDone, onCancel }: {
  row: BossReportRow; mode: "solve" | "message"; onDone: (note: string) => void; onCancel: () => void;
}) {
  const [text, setText] = useState(mode === "solve" ? SOLVED_TEXT : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    setBusy(true);
    setError("");
    try {
      if (mode === "solve") await setBossReportStatus(row.id, true, text.trim());
      else await messageBossReporter(row.id, text.trim());
      onDone(mode === "solve" ? `Marked solved and ${row.name} was told.` : `Message sent to ${row.name}.`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="boss-reply-box">
      <label>
        <span>{mode === "solve" ? `Message to ${row.name} (shown when they next open SkillDARA)` : `Message to ${row.name}`}</span>
        <textarea rows={3} maxLength={2000} value={text} autoFocus onChange={(e) => setText(e.target.value)}
          placeholder="Write your message to the learner…" />
      </label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="admin-row-actions">
        <button type="button" className="btn btn-primary btn-sm" disabled={busy || (mode === "message" && !text.trim())} onClick={() => void submit()}>
          {busy ? "Sending…" : mode === "solve" ? "Mark solved and send" : "Send message"}
        </button>
        <button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

/** Problems learners asked Boss to report. The first table counts each kind over
 * the last 30 days, so a problem that keeps coming back stands out. Each report
 * has a status; solving it, or messaging the learner, reaches them in the app. */
export default function BossReportsPanel() {
  const { data, error, loading, reload } = useLoad(() => fetchBossReports(), []);
  const [replying, setReplying] = useState<{ id: string; mode: "solve" | "message" } | null>(null);
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const [only, setOnly] = useState<{ kind: "user" | "agent"; id: string; label: string } | null>(null);

  async function reopen(row: BossReportRow) {
    setActionError("");
    try {
      await setBossReportStatus(row.id, false);
      setNotice("Report opened again.");
      reload();
    } catch (err) {
      setActionError((err as Error).message);
    }
  }

  const openCount = data?.reports.filter((row) => (row.status ?? "open") === "open").length ?? 0;
  const shown = (data?.reports ?? []).filter((row) => !only
    || (only.kind === "user" ? row.user_id === only.id : (row.agent_id || "") === only.id));
  const pick = (next: { kind: "user" | "agent"; id: string; label: string }) =>
    setOnly(only && only.kind === next.kind && only.id === next.id ? null : next);

  return (
    <div className="admin-section">
      {error && <div className="admin-error">{error} <button className="btn btn-outline btn-sm" onClick={reload}>Retry</button></div>}
      {actionError && <div className="admin-error">{actionError}</div>}
      {notice && <div className="boss-notice" role="status">{notice}</div>}
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
      <div className="boss-count-grid">
        <div className="admin-table-card">
          <table className="admin-table">
            <thead><tr><th>Learner</th><th>Reports</th><th>Open</th><th>Agents</th></tr></thead>
            <tbody>
              {data?.by_user?.map((row) => (
                <tr key={row.user_id} className={`boss-count-row${only?.kind === "user" && only.id === row.user_id ? " active" : ""}`}
                  onClick={() => pick({ kind: "user", id: row.user_id, label: row.name || row.email })} title="Show only this learner's reports">
                  <td className="admin-table-primary">{row.name}<br /><small>{row.email}</small></td>
                  <td><b>{row.reports}</b></td>
                  <td>{row.open}</td>
                  <td><small>{row.agents.map(agentLabel).join(", ") || "—"}</small></td>
                </tr>
              ))}
              {data && !data.by_user?.length && <tr><td colSpan={4} className="admin-table-empty">No reports yet.</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="admin-table-card">
          <table className="admin-table">
            <thead><tr><th>Agent</th><th>Reports</th><th>Open</th><th>Learners</th></tr></thead>
            <tbody>
              {data?.by_agent?.map((row) => (
                <tr key={row.agent_id || "none"} className={`boss-count-row${only?.kind === "agent" && only.id === row.agent_id ? " active" : ""}`}
                  onClick={() => pick({ kind: "agent", id: row.agent_id, label: row.agent_id ? agentLabel(row.agent_id) : "No agent" })} title="Show only this agent's reports">
                  <td className="admin-table-primary">{row.agent_id ? agentLabel(row.agent_id) : "No agent"}</td>
                  <td><b>{row.reports}</b></td>
                  <td>{row.open}</td>
                  <td>{row.learners}</td>
                </tr>
              ))}
              {data && !data.by_agent?.length && <tr><td colSpan={4} className="admin-table-empty">No reports yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      {data && (
        <p className="boss-open-count">
          {openCount} open · {data.reports.length - openCount} solved
          {only && <> · showing only <b>{only.label}</b> ({shown.length}) <button type="button" className="link-btn" onClick={() => setOnly(null)}>Show all</button></>}
        </p>
      )}
      <div className="admin-table-card">
        <table className="admin-table">
          <thead><tr><th>Learner</th><th>Kind</th><th>Agent</th><th>What they said</th><th>Received</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
            {shown.map((row) => {
              const solved = row.status === "solved";
              const replies = row.replies ?? [];
              return [
                <tr key={row.id}>
                  <td className="admin-table-primary">{row.name}<br /><small>{row.email}</small></td>
                  <td>{CATEGORIES[row.category] ?? row.category}</td>
                  <td>{row.agent_id ? agentLabel(row.agent_id) : "—"}</td>
                  <td style={{ maxWidth: 360, whiteSpace: "pre-wrap" }}>
                    {row.message || "—"}
                    {replies.map((reply) => (
                      <div key={reply.id} className="boss-reply-sent">
                        <b>Team:</b> {reply.body}
                        <small> · {formatDate(reply.created_at)} · {reply.read_at ? "seen" : "not seen yet"}</small>
                      </div>
                    ))}
                  </td>
                  <td>{formatDate(row.created_at)}</td>
                  <td>
                    <span className={`boss-status ${solved ? "solved" : "open"}`}>{solved ? "Solved" : "Open"}</span>
                    {solved && row.solved_at && <><br /><small>{formatDate(row.solved_at)}</small></>}
                  </td>
                  <td>
                    <div className="admin-row-actions">
                      {!solved && <button type="button" className="btn btn-primary btn-sm" onClick={() => { setNotice(""); setReplying({ id: row.id, mode: "solve" }); }}>Mark solved</button>}
                      <button type="button" className="btn btn-outline btn-sm" onClick={() => { setNotice(""); setReplying({ id: row.id, mode: "message" }); }}>Send message</button>
                      {solved && <button type="button" className="link-btn" onClick={() => void reopen(row)}>Reopen</button>}
                    </div>
                  </td>
                </tr>,
                replying?.id === row.id && (
                  <tr key={`${row.id}-reply`}>
                    <td colSpan={7}>
                      <ReplyBox row={row} mode={replying.mode} onCancel={() => setReplying(null)}
                        onDone={(note) => { setReplying(null); setNotice(note); reload(); }} />
                    </td>
                  </tr>
                ),
              ];
            })}
            {data && !data.reports.length && <tr><td colSpan={7} className="admin-table-empty">No reports yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
