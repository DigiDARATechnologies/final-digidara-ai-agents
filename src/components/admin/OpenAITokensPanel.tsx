import { useState } from "react";
import {
  fetchOpenAIAdminKey, fetchOpenAILive, fetchOpenAIPool, fetchOpenAIPoolUsers, removeOpenAIAdminKey, saveOpenAIAdminKey, saveOpenAIBalance,
} from "../../lib/adminApi";
import type { OpenAIPool } from "../../lib/adminApi";
import { formatDate, formatNumber } from "./adminFormat";
import { useLoad } from "./useLoad";

const PAGE = 25;
const BILLING_URL = "https://platform.openai.com/settings/organization/billing";
const usd = (value: number | null | undefined) =>
  value === null || value === undefined ? "—" : `$${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const tokens = (value: number | null | undefined) => (value === null || value === undefined ? "—" : formatNumber(value));

function Kpi({ label, value, note }: { label: string; value: string; note?: string }) {
  return <div className="admin-kpi"><span>{label}</span><strong>{value}</strong>{note && <small>{note}</small>}</div>;
}

function Status({ pool }: { pool: OpenAIPool }) {
  if (pool.status === "not_set") {
    return (
      <div className="admin-error">
        No OpenAI balance entered yet, so nobody can tell whether users' tokens are covered. Open the{" "}
        <a href={BILLING_URL} target="_blank" rel="noreferrer">OpenAI billing page</a>, copy the credit balance, and enter it below.
      </div>
    );
  }
  if (pool.status === "short") {
    return (
      <div className="admin-error">
        <strong>Not enough OpenAI credit.</strong> Users hold {tokens(pool.allocated_tokens)} tokens but the account can pay for only{" "}
        {tokens(pool.available_tokens)}: short by {tokens(pool.shortfall_tokens)} tokens
        (about {usd(((pool.shortfall_tokens ?? 0) / 1_000_000) * pool.usd_per_million_tokens)}).{" "}
        {pool.last_alert_at ? `${pool.support_email} was emailed ${formatDate(pool.last_alert_at)}.` : `Emailing ${pool.support_email} failed or is not set up (SMTP).`}
        {pool.new_users_while_short > 0 && ` ${pool.new_users_while_short} new user${pool.new_users_while_short === 1 ? "" : "s"} joined while short.`}
      </div>
    );
  }
  return (
    <div className="admin-success">
      Enough OpenAI credit for every user's tokens, with {tokens(pool.spare_tokens)} to spare: room for about{" "}
      {formatNumber(pool.new_users_room ?? 0)} more new users at {tokens(pool.new_user_tokens)} tokens each.
    </div>
  );
}

function BalanceForm({ onSaved }: { onSaved: (pool: OpenAIPool) => void }) {
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const value = Number(amount);
    if (!amount.trim() || !Number.isFinite(value) || value < 0) { setError("Enter the balance in US dollars, for example 120.50."); return; }
    setSaving(true);
    setError("");
    try {
      onSaved(await saveOpenAIBalance(value, note.trim()));
      setAmount("");
      setNote("");
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setSaving(false);
    }
  };
  return (
    <form className="admin-toolbar" onSubmit={submit}>
      <input className="admin-search" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)}
        placeholder="Credit balance in USD, e.g. 120.50" aria-label="OpenAI credit balance in US dollars" />
      <input className="admin-search" value={note} maxLength={255} onChange={(e) => setNote(e.target.value)}
        placeholder="Note (optional), e.g. topped up $100" aria-label="Note" />
      <button className="btn btn-primary btn-sm" type="submit" disabled={saving}>{saving ? "Saving…" : "Save balance"}</button>
      {error && <div className="admin-error">{error}</div>}
    </form>
  );
}

function UsersTable({ version }: { version: number }) {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [onlyShort, setOnlyShort] = useState(false);
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useLoad(
    () => fetchOpenAIPoolUsers({ search: query, only_short: onlyShort, page, limit: PAGE }), [query, onlyShort, page, version],
  );
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE)) : 1;
  return (
    <>
      <form className="admin-toolbar" onSubmit={(event) => { event.preventDefault(); setPage(1); setQuery(search.trim()); }}>
        <input className="admin-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by name or email" aria-label="Search users" />
        <label><input type="checkbox" checked={onlyShort} onChange={(e) => { setOnlyShort(e.target.checked); setPage(1); }} /> Only users not covered</label>
        <button className="btn btn-outline btn-sm" type="submit">Search</button>
      </form>
      {error && <div className="admin-error">{error} <button className="btn btn-outline btn-sm" onClick={reload}>Retry</button></div>}
      <div className="admin-table-card">
        <table className="admin-table">
          <thead><tr><th>User</th><th>Joined</th><th>Tokens given (left)</th><th>Tokens used</th><th>Covered by OpenAI credit</th></tr></thead>
          <tbody>
            {data?.users.map((u) => (
              <tr key={u.id}>
                <td className="admin-table-primary">{u.name}<br /><small>{u.email}</small></td>
                <td>{formatDate(u.created_at)}</td>
                <td>{formatNumber(Math.max(0, u.token_balance))}</td>
                <td>{formatNumber(u.used_tokens)}</td>
                <td>
                  {u.covered === null ? "—" : (
                    <span className={`admin-badge ${u.covered ? "badge-active" : "badge-rejected"}`}>{u.covered ? "covered" : "not covered"}</span>
                  )}
                </td>
              </tr>
            ))}
            {data && !data.users.length && <tr><td colSpan={5} className="admin-table-empty">No users match.</td></tr>}
            {loading && !data && <tr><td colSpan={5} className="admin-table-empty">Loading…</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="admin-toolbar">
        <button className="btn btn-outline btn-sm" disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>← Previous</button>
        <small className="admin-loading">Page {page} of {pages} · {data ? formatNumber(data.total) : 0} users · credit is counted to users in the order they joined, so existing users are covered first</small>
        <button className="btn btn-outline btn-sm" disabled={page >= pages || loading} onClick={() => setPage(page + 1)}>Next →</button>
      </div>
    </>
  );
}

const LIVE_ERRORS: Record<string, string> = {
  no_key: "Not connected to OpenAI yet. Paste an OpenAI admin key above; spending and tokens then come straight from OpenAI.",
  rejected: "OpenAI refused the admin key. Check that it is an admin key (sk-admin-…), not a normal API key, and that it has not been revoked; then change it above.",
  unavailable: "OpenAI did not answer just now. The figures below fall back to the agents' own usage; try Refresh in a minute.",
};

const ADMIN_KEYS_URL = "https://platform.openai.com/settings/organization/admin-keys";

/** Paste OpenAI's admin key here instead of editing the server's .env. The
 * server checks it with OpenAI, keeps it encrypted, and only ever sends back a
 * hint such as "sk-admin-…abcd". */
function AdminKeyForm({ onChanged }: { onChanged: () => void }) {
  const { data, error: loadError, reload } = useLoad(fetchOpenAIAdminKey, []);
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const act = async (run: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try {
      await run();
      setKey("");
      setEditing(false);
      reload();
      onChanged();
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const value = key.trim();
    if (!value.startsWith("sk-admin-")) { setError("Paste an OpenAI admin key: it starts with sk-admin-."); return; }
    void act(() => saveOpenAIAdminKey(value));
  };
  const showForm = editing || (data && !data.set);
  return (
    <div className="admin-table-card" style={{ padding: "1rem" }}>
      <strong>OpenAI admin key</strong>
      {loadError && <div className="admin-error">{loadError}</div>}
      {data?.set && (
        <p className="admin-loading">
          <span className="admin-badge badge-active">connected</span>{" "}
          <code>{data.hint}</code>{" "}
          {data.source === "page"
            ? `saved on this page${data.updated_at ? ` ${formatDate(data.updated_at)}` : ""}`
            : "from the server's .env (OPENAI_ADMIN_KEY)"}
          {!editing && (
            <>
              {" "}<button className="btn btn-outline btn-sm" type="button" onClick={() => setEditing(true)}>Change key</button>
              {data.source === "page" && (
                <button className="btn btn-outline btn-sm" type="button" disabled={busy}
                  onClick={() => { if (window.confirm("Remove the OpenAI admin key saved on this page?")) void act(removeOpenAIAdminKey); }}>
                  Remove
                </button>
              )}
            </>
          )}
        </p>
      )}
      {showForm && (
        <>
          <p className="admin-loading">
            Create one at <a href={ADMIN_KEYS_URL} target="_blank" rel="noreferrer">OpenAI → Organization → Admin keys</a> (read
            access is enough) and paste it here. It is checked with OpenAI, stored encrypted, and never shown again.
          </p>
          <form className="admin-toolbar" onSubmit={submit}>
            <input className="admin-search" type="password" autoComplete="off" spellCheck={false} value={key}
              onChange={(e) => setKey(e.target.value)} placeholder="sk-admin-…" aria-label="OpenAI admin key" />
            <button className="btn btn-primary btn-sm" type="submit" disabled={busy || !key.trim()}>
              {busy ? "Checking with OpenAI…" : "Save key"}
            </button>
            {editing && <button className="btn btn-outline btn-sm" type="button" onClick={() => { setEditing(false); setError(""); setKey(""); }}>Cancel</button>}
          </form>
        </>
      )}
      {error && <div className="admin-error">{error}</div>}
    </div>
  );
}

/** Spending and tokens pulled from the OpenAI platform itself, every 10 minutes. */
function LiveFromOpenAI({ version, onKeyChanged }: { version: number; onKeyChanged: () => void }) {
  const [refresh, setRefresh] = useState(0);
  const { data, error, loading } = useLoad(() => fetchOpenAILive(refresh > 0), [refresh, version]);
  return (
    <>
      <div className="admin-toolbar">
        <h4>Live from OpenAI</h4>
        {data?.fetched_at && <small className="admin-loading">Pulled from OpenAI {formatDate(data.fetched_at)} (every 10 minutes)</small>}
        <button className="btn btn-outline btn-sm" onClick={() => setRefresh((n) => n + 1)} disabled={loading}>
          {loading ? "Pulling…" : "Pull now"}
        </button>
      </div>
      <AdminKeyForm onChanged={() => { setRefresh((n) => n + 1); onKeyChanged(); }} />
      {error && <div className="admin-error">{error}</div>}
      {data && !data.connected && <div className="admin-error">{LIVE_ERRORS[data.error ?? "unavailable"]}</div>}
      {data?.connected && (
        <>
          <div className="admin-kpis">
            <Kpi label="Spent today" value={usd(data.today_usd)} note="UTC day, from OpenAI" />
            <Kpi label="Spent this month" value={usd(data.month_usd)} />
            <Kpi label={`Last ${data.days} days`} value={usd(data.period_usd)}
              note={`${tokens(data.period_tokens)} tokens · ${formatNumber(data.period_requests ?? 0)} requests`} />
          </div>
          {!!data.by_model?.length && (
            <div className="admin-table-card">
              <table className="admin-table">
                <thead><tr><th>Model (last {data.days} days)</th><th>Input tokens</th><th>Output tokens</th><th>Requests</th></tr></thead>
                <tbody>{data.by_model.map((m) => (
                  <tr key={m.model}><td className="admin-table-primary">{m.model}</td><td>{tokens(m.input_tokens)}</td><td>{tokens(m.output_tokens)}</td><td>{formatNumber(m.requests)}</td></tr>
                ))}</tbody>
              </table>
            </div>
          )}
          {!!data.by_line_item?.length && (
            <div className="admin-table-card">
              <table className="admin-table">
                <thead><tr><th>Charged for (last {data.days} days)</th><th>Cost</th></tr></thead>
                <tbody>{data.by_line_item.map((l) => <tr key={l.line_item}><td>{l.line_item}</td><td className="admin-table-primary">{usd(l.usd)}</td></tr>)}</tbody>
              </table>
            </div>
          )}
          <details>
            <summary>Day by day</summary>
            <div className="admin-table-card">
              <table className="admin-table">
                <thead><tr><th>Day (UTC)</th><th>Cost</th><th>Tokens</th><th>Requests</th></tr></thead>
                <tbody>{data.daily?.map((d) => (
                  <tr key={d.date}><td>{d.date}</td><td className="admin-table-primary">{usd(d.usd)}</td><td>{tokens(d.input_tokens + d.output_tokens)}</td><td>{formatNumber(d.requests)}</td></tr>
                ))}</tbody>
              </table>
            </div>
          </details>
        </>
      )}
    </>
  );
}

/** OpenAI's prepaid credit against the tokens SkillDARA has given its users.
 * OpenAI has no API for the balance itself, so an admin enters it after each
 * top-up; the server takes off what was spent since (see billing/openai_pool.py). */
export default function OpenAITokensPanel() {
  const { data, error, loading, reload } = useLoad(fetchOpenAIPool, []);
  const [saved, setSaved] = useState<OpenAIPool | null>(null);
  const [version, setVersion] = useState(0);
  const pool = saved && (!data || saved.generated_at > data.generated_at) ? saved : data;
  if (loading && !pool) return <p className="admin-loading">Loading OpenAI tokens…</p>;
  if (error && !pool) return <div className="admin-error">{error} <button className="btn btn-outline btn-sm" onClick={reload}>Retry</button></div>;
  if (!pool) return null;
  const entry = pool.balance_entry;
  return (
    <div className="admin-section">
      <div className="admin-toolbar">
        <small className="admin-loading">Updated {formatDate(pool.generated_at)}</small>
        <button className="btn btn-outline btn-sm" onClick={() => { setSaved(null); reload(); setVersion((v) => v + 1); }} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>
      <Status pool={pool} />

      <h4>OpenAI account</h4>
      <div className="admin-kpis">
        <Kpi label="Credit left" value={usd(pool.remaining_usd)}
          note={entry ? `${usd(entry.balance_usd)} entered ${formatDate(entry.created_at)}` : "no balance entered"} />
        <Kpi label="Spent since then" value={entry ? usd(pool.spent_usd) : "—"}
          note={entry
            ? (pool.spend_source === "openai" ? "exact, from OpenAI" : "estimated from agents' usage")
            : (pool.exact_costs ? "OpenAI admin key connected" : "OpenAI admin key not set")} />
        <Kpi label="Tokens available" value={tokens(pool.available_tokens)} note={`at $${pool.usd_per_million_tokens} per million (gpt-4o-mini)`} />
      </div>

      <LiveFromOpenAI version={version} onKeyChanged={reload} />

      <h4>Given to users</h4>
      <div className="admin-kpis">
        <Kpi label="Tokens held by users" value={tokens(pool.allocated_tokens)}
          note={`${formatNumber(pool.users_holding_tokens)} of ${formatNumber(pool.users_total)} users hold tokens`} />
        <Kpi label={pool.status === "short" ? "Short by" : "Spare"}
          value={tokens(pool.status === "short" ? pool.shortfall_tokens : pool.spare_tokens)}
          note={pool.status === "short" ? "tokens OpenAI cannot pay for" : "left after every user's tokens"} />
        <Kpi label="Each new user gets" value={tokens(pool.new_user_tokens)}
          note={pool.new_users_room === null ? "" : `room for ~${formatNumber(pool.new_users_room)} more`} />
      </div>

      <h4>Enter the OpenAI balance</h4>
      <p className="admin-loading">
        After each top-up, copy the credit balance from the <a href={BILLING_URL} target="_blank" rel="noreferrer">OpenAI billing page</a>.{" "}
        {pool.exact_costs
          ? "Spending after it is read from OpenAI itself."
          : "Spending after it is estimated from what agents report; save an OpenAI admin key under Live from OpenAI for exact figures."}{" "}
        When the credit does not cover users' tokens, {pool.support_email} is emailed at once and every 12 hours until it does.
      </p>
      <BalanceForm onSaved={(next) => { setSaved(next); setVersion((v) => v + 1); }} />
      {pool.entries.length > 0 && (
        <div className="admin-table-card">
          <table className="admin-table">
            <thead><tr><th>Entered</th><th>Balance</th><th>Note</th></tr></thead>
            <tbody>{pool.entries.map((e) => <tr key={e.id}><td>{formatDate(e.created_at)}</td><td className="admin-table-primary">{usd(e.balance_usd)}</td><td>{e.note || "—"}</td></tr>)}</tbody>
          </table>
        </div>
      )}

      <h4>Every user's tokens</h4>
      <UsersTable version={version} />
    </div>
  );
}
