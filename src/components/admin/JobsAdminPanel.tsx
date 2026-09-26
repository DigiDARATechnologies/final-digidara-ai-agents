import { useEffect, useState } from "react";
import {
  adminAdzunaRun,
  adminApifyActors,
  adminApifyRun,
  adminGetAutomation,
  adminJSearchRun,
  adminListCategories,
  adminListJobs,
  adminListRuns,
  adminListSources,
  adminListUsers,
  adminRunSource,
  adminUpdateAutomation,
  adminUpdateJobStatus,
  adminBulkUpdateJobStatus,
  adminUpdatePlan,
  type ApifyActor,
  type IngestionRun,
  type JobAutomationSettings,
} from "../../lib/jobFetchApi";


const PLATFORM_LABELS: Record<string, string> = {
  naukri: "Naukri", linkedin: "LinkedIn", indeed: "Indeed", glassdoor: "Glassdoor", foundit: "Foundit",
  hirist: "Hirist", instahyre: "Instahyre", internshala: "Internshala",
};

type Tab = "jobs" | "sources" | "users";

const STATUS_BADGE_CLASS: Record<string, string> = {
  pending: "badge-pending",
  active: "badge-active",
  rejected: "badge-rejected",
  expired: "badge-expired",
  discovered: "badge-pending",
  validating: "badge-pending",
  empty_board: "badge-expired",
  no_matching_jobs: "badge-expired",
  temporarily_failed: "badge-rejected",
  invalid: "badge-rejected",
  disabled: "badge-expired",
  queued: "badge-pending",
  running: "badge-pending",
  completed: "badge-active",
  failed: "badge-rejected",
};

function StatusBadge({ status }: { status: string }) {
  return <span className={`admin-badge ${STATUS_BADGE_CLASS[status] || "badge-expired"}`}>{status.replace(/_/g, " ")}</span>;
}

function getJobSourceBadge(externalId: string = "") {
  if (externalId.startsWith("adzuna:")) return { label: "Adzuna", color: "#0369a1", bg: "#e0f2fe" };
  if (externalId.startsWith("jsearch:")) return { label: "JSearch (LinkedIn/Indeed)", color: "#047857", bg: "#d1fae5" };
  if (externalId.startsWith("manual")) return { label: "Manual", color: "#4b5563", bg: "#f3f4f6" };
  return { label: "Direct", color: "#6b7280", bg: "#f3f4f6" };
}

export default function JobsAdminPanel() {
  const [tab, setTab] = useState<Tab>("jobs");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [jobs, setJobs] = useState<Array<Record<string, any>>>([]);
  const [jobStatusFilter, setJobStatusFilter] = useState("active");
  const [jobCategoryFilter, setJobCategoryFilter] = useState("");
  const [jobSourceFilter, setJobSourceFilter] = useState("");
  const [jobLocationFilter, setJobLocationFilter] = useState("");
  const [locationInput, setLocationInput] = useState("");
  const [categories, setCategories] = useState<Array<{ id: string; label: string }>>([]);


  const [sources, setSources] = useState<Array<Record<string, any>>>([]);
  const [users, setUsers] = useState<Array<Record<string, any>>>([]);
  const [apifyActors, setApifyActors] = useState<ApifyActor[]>([]);
  const [runs, setRuns] = useState<IngestionRun[]>([]);
  const [runningPlatform, setRunningPlatform] = useState<string | null>(null);
  const [automation, setAutomation] = useState<JobAutomationSettings | null>(null);
  const [automationLoading, setAutomationLoading] = useState(false);

  function loadJobs(status = jobStatusFilter, category = jobCategoryFilter, location = jobLocationFilter) {
    setLoading(true);
    setError(null);
    adminListJobs({ status: status || undefined, category: category || undefined, location: location || undefined })
      .then((r) => setJobs(r.jobs))
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }

  function load(nextTab: Tab) {
    setLoading(true);
    setError(null);
    const request =
      nextTab === "jobs"
        ? adminListJobs({ status: jobStatusFilter || undefined }).then((r) => setJobs(r.jobs))
        : nextTab === "sources"
          ? Promise.all([adminListSources(), adminApifyActors(), adminListRuns(), adminGetAutomation()]).then(([s, a, r, auto]) => {
              setSources(s.sources);
              setApifyActors(a.actors);
              setRuns(r.runs);
              setAutomation(auto.automation);
            })
          : adminListUsers().then((r) => setUsers(r.users));
    request.catch((err) => setError((err as Error).message)).finally(() => setLoading(false));
  }

  useEffect(() => {
    load(tab);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  useEffect(() => {
    adminListCategories().then((r) => setCategories(r.categories)).catch(() => {});
    adminGetAutomation().then((r) => setAutomation(r.automation)).catch(() => {});
  }, []);

  // Poll only while this tab has queued/running work. The HTTP request that
  // starts collection returns immediately; these status reads provide the
  // admin with durable progress from job_ingestion_runs.
  useEffect(() => {
    if (tab !== "sources" || !runs.some((run) => run.status === "queued" || run.status === "running")) return;
    let active = true;
    const timer = window.setTimeout(() => {
      Promise.all([adminListSources(), adminApifyActors(), adminListRuns(), adminGetAutomation()])
        .then(([s, a, r, auto]) => {
          if (!active) return;
          setSources(s.sources);
          setApifyActors(a.actors);
          setRuns(r.runs);
          setAutomation(auto.automation);
        })
        .catch((err) => active && setError((err as Error).message));
    }, 3000);
    return () => { active = false; window.clearTimeout(timer); };
  }, [tab, runs]);

  async function handleToggleAutomation(nextEnabled: boolean) {
    setAutomationLoading(true);
    setError(null);
    try {
      const result = await adminUpdateAutomation(nextEnabled);
      setAutomation(result.automation);
      setNotice(
        nextEnabled
          ? "Daily automated job fetching is turned ON. The server will fetch fresh jobs every day at 9:00 AM IST."
          : "Daily automated job fetching is turned OFF. Automated daily ingestion is paused."
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setAutomationLoading(false);
    }
  }


  async function moderate(jobId: number, status: "active" | "rejected") {
    try {
      await adminUpdateJobStatus(jobId, status);
      setJobs((prev) => prev.map((job) => job.id === jobId ? { ...job, status } : job));
      setNotice(`Job #${jobId} status updated to ${status}.`);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function changePlan(userId: string, planTier: "free" | "pro") {
    try {
      await adminUpdatePlan(userId, planTier);
      setUsers((prev) => prev.map((u) => (u.user_id === userId ? { ...u, plan_tier: planTier } : u)));
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function runSource(sourceId: number) {
    try {
      setError(null);
      const result = await adminRunSource(sourceId);
      setNotice(result.message);
      load("sources");
    } catch (err) {
      setError((err as Error).message);
    }
  }


  async function syncAndRunAdzuna() {
    try {
      setLoading(true);
      setError(null);
      const result = await adminAdzunaRun();
      setNotice(`${result.queued_count} Adzuna regional query source(s) queued; ${result.already_queued_count} already active.`);
      load("sources");
    } catch (err) {
      setError((err as Error).message);
      setLoading(false);
    }
  }

  async function syncAndRunJSearch() {
    try {
      setLoading(true);
      setError(null);
      const result = await adminJSearchRun();
      setNotice(`${result.queued_count} JSearch RapidAPI source(s) queued; ${result.already_queued_count} already active.`);
      load("sources");
    } catch (err) {
      setError((err as Error).message);
      setLoading(false);
    }
  }


  /** Manual, per-platform — never automatic, per the admin's own request:
   * click "Run" for exactly the one platform you want fetched right now. */
  async function runApifyPlatform(platform: string) {
    setRunningPlatform(platform);
    setError(null);
    try {
      const result = await adminApifyRun(platform);
      setNotice(`${PLATFORM_LABELS[platform] || platform} queued for background ingestion${result.already_queued_count ? " (an existing run was already active)" : ""}.`);
      load("sources");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setRunningPlatform(null);
    }
  }

  function applyLocationFilter() {
    setJobLocationFilter(locationInput);
    loadJobs(jobStatusFilter, jobCategoryFilter, locationInput);
  }

  function clearJobFilters() {
    setJobStatusFilter("active");
    setJobCategoryFilter("");
    setJobSourceFilter("");
    setJobLocationFilter("");
    setLocationInput("");
    loadJobs("active", "", "");
  }

  const activeSourceIds = new Set(
    runs.filter((run) => run.status === "queued" || run.status === "running").map((run) => run.source_id),
  );

  const filteredJobs = jobs.filter((job) => {
    if (!jobSourceFilter) return true;
    const extId = (job.external_id || "").toLowerCase();
    if (jobSourceFilter === "adzuna") return extId.startsWith("adzuna:");
    if (jobSourceFilter === "jsearch") return extId.startsWith("jsearch:");
    if (jobSourceFilter === "manual") return extId.startsWith("manual");
    return true;
  });

  return (
    <div className="admin-panel">
      <div className="admin-panel-tabs">
        <button className={`admin-tab${tab === "jobs" ? " active" : ""}`} onClick={() => setTab("jobs")}>Jobs &amp; Postings</button>
        <button className={`admin-tab${tab === "sources" ? " active" : ""}`} onClick={() => setTab("sources")}>
          Sources &amp; Automation
          {automation && (
            <span
              style={{
                display: "inline-block",
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                marginLeft: "8px",
                backgroundColor: automation.enabled ? "#16a34a" : "#9ca3af",
                verticalAlign: "middle"
              }}
              title={automation.enabled ? "Daily Automation: ON (9:00 AM IST)" : "Daily Automation: OFF"}
            />
          )}
        </button>
        <button className={`admin-tab${tab === "users" ? " active" : ""}`} onClick={() => setTab("users")}>Users &amp; plans</button>
      </div>

      {error && <div className="admin-error">{error}</div>}
      {notice && <div className="admin-success">{notice}</div>}

      {tab === "jobs" && (
        <div className="admin-section">
          <div className="admin-filter-bar">
            <div className="admin-filter-field">
              <label>Status</label>
              <select value={jobStatusFilter} onChange={(e) => { setJobStatusFilter(e.target.value); loadJobs(e.target.value, jobCategoryFilter, jobLocationFilter); }}>
                <option value="active">Active (Ready for Agent)</option>
                <option value="">All statuses</option>
                <option value="pending">Pending</option>
                <option value="rejected">Rejected / Inactive</option>
                <option value="expired">Expired</option>
              </select>
            </div>
            <div className="admin-filter-field">
              <label>Source</label>
              <select value={jobSourceFilter} onChange={(e) => setJobSourceFilter(e.target.value)}>
                <option value="">All Sources</option>
                <option value="adzuna">Adzuna</option>
                <option value="jsearch">RapidAPI (LinkedIn/Indeed)</option>
                <option value="manual">Manual</option>
              </select>
            </div>
            <div className="admin-filter-field">
              <label>Category</label>
              <select value={jobCategoryFilter} onChange={(e) => { setJobCategoryFilter(e.target.value); loadJobs(jobStatusFilter, e.target.value, jobLocationFilter); }}>
                <option value="">All Categories</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>{c.label}</option>
                ))}
              </select>
            </div>
            <div className="admin-filter-field admin-filter-field-grow">
              <label>Location</label>
              <div className="admin-filter-inline">
                <input
                  type="text"
                  placeholder="e.g. Chennai"
                  value={locationInput}
                  onChange={(e) => setLocationInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && applyLocationFilter()}
                />
                <button className="btn btn-outline btn-sm" onClick={applyLocationFilter}>Apply</button>
              </div>
            </div>
            <button className="admin-filter-clear" onClick={clearJobFilters}>Clear Filters</button>
          </div>

          <div
            style={{
              padding: "10px 16px",
              marginTop: "14px",
              marginBottom: "14px",
              borderRadius: "8px",
              background: "rgba(16, 185, 129, 0.08)",
              border: "1px solid rgba(16, 185, 129, 0.25)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "10px",
            }}
          >
            <div style={{ fontSize: "12.5px", color: "var(--canvas-text)", display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "15px" }}>⚡</span>
              <span>
                <strong>Auto-Active Pipeline:</strong> All fetched jobs automatically update to <strong>Active</strong> and are instantly available for candidate matching. Manual admin approval is not required.
              </span>
            </div>
            {filteredJobs.some((j) => j.status === "pending") && (
              <button
                className="btn btn-primary btn-sm"
                onClick={async () => {
                  try {
                    setLoading(true);
                    const res = await adminBulkUpdateJobStatus("all_pending", "active");
                    setNotice(`${res.updated || "All"} pending job(s) successfully activated!`);
                    loadJobs(jobStatusFilter, jobCategoryFilter, jobLocationFilter);
                  } catch (err) {
                    setError((err as Error).message);
                  } finally {
                    setLoading(false);
                  }
                }}
              >
                ⚡ Activate All Pending Jobs
              </button>
            )}
          </div>

          {loading ? (
            <div className="admin-loading">Loading…</div>
          ) : (
            <div className="admin-table-card">
              <table className="admin-table">
                <thead><tr><th>Title</th><th>Company</th><th>Source</th><th>Location</th><th>Category</th><th>Status</th><th>Actions</th></tr></thead>
                <tbody>
                  {filteredJobs.map((job) => {
                    const badge = getJobSourceBadge(job.external_id);
                    return (
                      <tr key={job.id}>
                        <td className="admin-table-primary">{job.title}</td>
                        <td>{job.company}</td>
                        <td>
                          <span
                            style={{
                              display: "inline-block",
                              padding: "2px 8px",
                              borderRadius: "4px",
                              fontSize: "12px",
                              fontWeight: 500,
                              color: badge.color,
                              backgroundColor: badge.bg,
                              border: `1px solid ${badge.color}33`,
                              whiteSpace: "nowrap"
                            }}
                          >
                            {badge.label}
                          </span>
                        </td>
                        <td>{job.location || "—"}</td>
                        <td>{job.category || "—"}</td>
                        <td><StatusBadge status={job.status} /></td>
                        <td>
                          <div className="admin-row-actions">
                            {job.status === "active" && (
                              <button className="btn btn-danger btn-sm" onClick={() => moderate(job.id, "rejected")}>Deactivate</button>
                            )}
                            {job.status === "pending" && (
                              <>
                                <button className="btn btn-primary btn-sm" onClick={() => moderate(job.id, "active")}>Activate</button>
                                <button className="btn btn-danger btn-sm" onClick={() => moderate(job.id, "rejected")}>Reject</button>
                              </>
                            )}
                            {(job.status === "rejected" || job.status === "expired") && (
                              <button className="btn btn-outline btn-sm" onClick={() => moderate(job.id, "active")}>Reactivate</button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                  {!filteredJobs.length && <tr><td colSpan={7} className="admin-table-empty">No jobs match these filters.</td></tr>}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {loading && tab !== "jobs" && <div className="admin-loading">Loading…</div>}

      {!loading && tab === "sources" && (
        <div className="admin-section">
          {/* Daily Automated Job Ingestion (9:00 AM IST) Card */}
          <div
            className="admin-card"
            style={{
              padding: "18px 22px",
              marginBottom: "22px",
              borderRadius: "12px",
              border: "1px solid var(--border)",
              background: "var(--card-bg, #ffffff)",
              boxShadow: "0 2px 10px rgba(0,0,0,0.04)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "18px",
            }}
          >
            <div style={{ flex: "1 1 360px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
                <h4 style={{ margin: 0, fontSize: "16px", fontWeight: 700 }}>
                  ⏰ Daily Automated Job Ingestion (9:00 AM IST)
                </h4>
                {automation?.enabled ? (
                  <span className="admin-badge badge-active" style={{ fontSize: "11px" }}>
                    ● Active (9:00 AM daily)
                  </span>
                ) : (
                  <span className="admin-badge badge-expired" style={{ fontSize: "11px" }}>
                    ○ Paused
                  </span>
                )}
              </div>
              <p style={{ margin: "0 0 12px 0", fontSize: "13px", color: "var(--text-dim, #666)", lineHeight: 1.45 }}>
                When enabled, the server automatically fetches fresh entry-level &amp; fresher jobs every day at{" "}
                <strong>9:00 AM IST</strong> across Adzuna, JSearch (RapidAPI), and Greenhouse, and prunes listings older than 30 days.
              </p>
              <div
                style={{
                  display: "flex",
                  gap: "18px",
                  fontSize: "12px",
                  color: "var(--text-dim, #666)",
                  flexWrap: "wrap",
                }}
              >
                <div>
                  <strong>Schedule:</strong> {automation?.schedule_time || "09:00"} ({automation?.timezone || "Asia/Kolkata"})
                </div>
                <div>
                  <strong>Last scheduled date:</strong>{" "}
                  {automation?.last_scheduled_date ? String(automation.last_scheduled_date) : "None yet"}
                </div>
                <div>
                  <strong>Last completed:</strong>{" "}
                  {automation?.last_completed_at
                    ? new Date(automation.last_completed_at).toLocaleString()
                    : "Never"}
                </div>
                <div>
                  <strong>Jobs queued in last run:</strong> {automation?.last_queued_count ?? 0}
                </div>
              </div>
              {automation?.last_error && (
                <div style={{ marginTop: "8px", fontSize: "12px", color: "#dc2626" }}>
                  <strong>Last error:</strong> {automation.last_error}
                </div>
              )}
            </div>

            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-end",
                gap: "8px",
                flexShrink: 0,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span
                  style={{
                    fontSize: "13.5px",
                    fontWeight: 700,
                    color: automation?.enabled ? "#16a34a" : "var(--text-dim, #666)",
                  }}
                >
                  {automationLoading ? "Updating…" : automation?.enabled ? "Daily Automation ON" : "Daily Automation OFF"}
                </span>
                <label className="switch" style={{ margin: 0, cursor: automationLoading ? "not-allowed" : "pointer" }}>
                  <input
                    type="checkbox"
                    checked={Boolean(automation?.enabled)}
                    disabled={automationLoading || !automation}
                    onChange={(e) => handleToggleAutomation(e.target.checked)}
                  />
                  <span className="slider"></span>
                </label>
              </div>
              <small style={{ fontSize: "11px", color: "var(--text-faint, #999)" }}>
                {automation?.enabled ? "Runs day-by-day at 09:00 AM IST" : "Toggle ON to resume automated daily fetching"}
              </small>
            </div>
          </div>

          <div className="admin-toolbar" style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
            <button className="btn btn-primary btn-sm" onClick={syncAndRunAdzuna} disabled={loading}>
              {loading ? "Queueing…" : "⚡ Sync + queue Adzuna (Tamil Nadu & Metros)"}
            </button>
            <button className="btn btn-primary btn-sm" onClick={syncAndRunJSearch} disabled={loading}>
              {loading ? "Queueing…" : "🔍 Sync + queue JSearch (RapidAPI)"}
            </button>
          </div>

          <h4>Configured Sources</h4>
          <div className="admin-table-card">
            <table className="admin-table">
              <thead><tr><th>Name</th><th>Type</th><th>Status</th><th>Last Run</th><th>Actions</th></tr></thead>
              <tbody>
                {sources.filter((s) => s.source_type !== "greenhouse").map((source) => (
                  <tr key={source.id}>
                    <td className="admin-table-primary">{source.name}</td>
                    <td>{source.source_type}</td>
                    <td><StatusBadge status={source.status} /></td>
                    <td>{source.last_run_at ? new Date(source.last_run_at).toLocaleString() : "never"}</td>
                    <td>
                      <button className="btn btn-outline btn-sm" disabled={activeSourceIds.has(source.id)} onClick={() => runSource(source.id)}>
                        {activeSourceIds.has(source.id) ? "Queued / running" : "Queue run"}
                      </button>
                    </td>
                  </tr>
                ))}
                {!sources.filter((s) => s.source_type !== "greenhouse").length && <tr><td colSpan={5} className="admin-table-empty">No active sources configured yet.</td></tr>}
              </tbody>
            </table>
          </div>


          <h4>Job boards (Apify — manual only, never scheduled)</h4>
          <div className="admin-table-card">
            <table className="admin-table">
              <thead><tr><th>Platform</th><th>Status</th><th>Jobs Fetched</th><th>Last Run</th><th>Last Error</th><th>Actions</th></tr></thead>
              <tbody>
                {apifyActors.map((actor) => (
                  <tr key={actor.platform}>
                    <td className="admin-table-primary">{PLATFORM_LABELS[actor.platform] || actor.platform}</td>
                    <td><StatusBadge status={actor.configured ? actor.status : "disabled"} /></td>
                    <td>{actor.last_fetched_count ?? "—"}</td>
                    <td>{actor.last_run_at ? new Date(actor.last_run_at).toLocaleString() : "never"}</td>
                    <td>{actor.last_error || "—"}</td>
                    <td>
                      <button
                        className="btn btn-primary btn-sm"
                        disabled={!actor.configured || runningPlatform === actor.platform || (actor.source_id !== null && activeSourceIds.has(actor.source_id))}
                        title={actor.configured ? undefined : "No actor id configured yet for this platform"}
                        onClick={() => runApifyPlatform(actor.platform)}
                      >
                        {runningPlatform === actor.platform
                          ? "Queueing…"
                          : actor.source_id !== null && activeSourceIds.has(actor.source_id)
                            ? "Queued / running"
                            : "Queue run"}
                      </button>
                    </td>
                  </tr>
                ))}
                {!apifyActors.length && <tr><td colSpan={6} className="admin-table-empty">No job-board actors configured yet.</td></tr>}
              </tbody>
            </table>
          </div>

          <h4>Recent Ingestion Runs</h4>
          <div className="admin-table-card">
            <table className="admin-table">
              <thead><tr><th>Source</th><th>Status</th><th>Queued</th><th>Fetched</th><th>Inserted</th><th>Updated</th><th>Error</th></tr></thead>
              <tbody>
                {runs.slice(0, 25).map((run) => (
                  <tr key={run.id}>
                    <td className="admin-table-primary">{run.source_name}</td>
                    <td><StatusBadge status={run.status} /></td>
                    <td>{new Date(run.queued_at).toLocaleString()}</td>
                    <td>{run.fetched_count}</td>
                    <td>{run.inserted_count}</td>
                    <td>{run.updated_count}</td>
                    <td>{run.error_message || "—"}</td>
                  </tr>
                ))}
                {!runs.length && <tr><td colSpan={7} className="admin-table-empty">No ingestion runs yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!loading && tab === "users" && (
        <div className="admin-section">
          <div className="admin-table-card">
            <table className="admin-table">
              <thead><tr><th>User</th><th>Plan</th><th>Profile Complete</th><th>Joined</th><th>Actions</th></tr></thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.user_id}>
                    <td className="admin-table-primary">{u.user_id}</td>
                    <td><span className={`admin-badge ${u.plan_tier === "pro" ? "badge-active" : "badge-expired"}`}>{u.plan_tier}</span></td>
                    <td>{u.profile_completed ? "Yes" : "No"}</td>
                    <td>{u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}</td>
                    <td>
                      <button className="btn btn-outline btn-sm" onClick={() => changePlan(u.user_id, u.plan_tier === "pro" ? "free" : "pro")}>
                        {u.plan_tier === "pro" ? "Downgrade to Free" : "Upgrade to Pro"}
                      </button>
                    </td>
                  </tr>
                ))}
                {!users.length && <tr><td colSpan={5} className="admin-table-empty">No user profiles yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
