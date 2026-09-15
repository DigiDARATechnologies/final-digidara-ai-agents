import { useEffect, useState } from "react";
import {
  adminApifyActors,
  adminApifyRun,
  adminGetAutomation,
  adminGreenhouseCompanies,
  adminGreenhouseRun,
  adminListCategories,
  adminListJobs,
  adminListRuns,
  adminListSources,
  adminListUsers,
  adminRunSource,
  adminUpdateJobStatus,
  adminUpdateAutomation,
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

export default function JobsAdminPanel() {
  const [tab, setTab] = useState<Tab>("jobs");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [jobs, setJobs] = useState<Array<Record<string, any>>>([]);
  const [jobStatusFilter, setJobStatusFilter] = useState("pending");
  const [jobCategoryFilter, setJobCategoryFilter] = useState("");
  const [jobLocationFilter, setJobLocationFilter] = useState("");
  const [locationInput, setLocationInput] = useState("");
  const [categories, setCategories] = useState<Array<{ id: string; label: string }>>([]);

  const [sources, setSources] = useState<Array<Record<string, any>>>([]);
  const [companies, setCompanies] = useState<Array<Record<string, any>>>([]);
  const [users, setUsers] = useState<Array<Record<string, any>>>([]);
  const [apifyActors, setApifyActors] = useState<ApifyActor[]>([]);
  const [runs, setRuns] = useState<IngestionRun[]>([]);
  const [runningPlatform, setRunningPlatform] = useState<string | null>(null);
  const [automation, setAutomation] = useState<JobAutomationSettings | null>(null);

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
          ? Promise.all([adminListSources(), adminGreenhouseCompanies(), adminApifyActors(), adminListRuns(), adminGetAutomation()]).then(([s, c, a, r, automationResult]) => {
              setSources(s.sources);
              setCompanies(c.companies);
              setApifyActors(a.actors);
              setRuns(r.runs);
              setAutomation(automationResult.automation);
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
  }, []);

  // Poll only while this tab has queued/running work. The HTTP request that
  // starts collection returns immediately; these status reads provide the
  // admin with durable progress from job_ingestion_runs.
  useEffect(() => {
    if (tab !== "sources" || !runs.some((run) => run.status === "queued" || run.status === "running")) return;
    let active = true;
    const timer = window.setTimeout(() => {
      Promise.all([adminListSources(), adminGreenhouseCompanies(), adminApifyActors(), adminListRuns()])
        .then(([s, c, a, r]) => {
          if (!active) return;
          setSources(s.sources);
          setCompanies(c.companies);
          setApifyActors(a.actors);
          setRuns(r.runs);
        })
        .catch((err) => active && setError((err as Error).message));
    }, 3000);
    return () => { active = false; window.clearTimeout(timer); };
  }, [tab, runs]);

  async function moderate(jobId: number, status: "active" | "rejected") {
    try {
      await adminUpdateJobStatus(jobId, status);
      setJobs((prev) => prev.filter((job) => job.id !== jobId));
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

  async function syncAndRunGreenhouse() {
    try {
      setLoading(true);
      setError(null);
      const result = await adminGreenhouseRun();
      setNotice(`${result.queued_count} Greenhouse source(s) queued; ${result.already_queued_count} already queued or running.`);
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

  async function toggleAutomation() {
    if (!automation) return;
    try {
      setError(null);
      const result = await adminUpdateAutomation(!automation.enabled);
      setAutomation(result.automation);
      setNotice(result.automation.enabled ? "Daily Greenhouse automation enabled." : "Daily Greenhouse automation disabled. Manual runs remain available.");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function applyLocationFilter() {
    setJobLocationFilter(locationInput);
    loadJobs(jobStatusFilter, jobCategoryFilter, locationInput);
  }

  function clearJobFilters() {
    setJobStatusFilter("pending");
    setJobCategoryFilter("");
    setJobLocationFilter("");
    setLocationInput("");
    loadJobs("pending", "", "");
  }

  const activeSourceIds = new Set(
    runs.filter((run) => run.status === "queued" || run.status === "running").map((run) => run.source_id),
  );

  return (
    <div className="admin-panel">
      <div className="admin-panel-tabs">
        <button className={`admin-tab${tab === "jobs" ? " active" : ""}`} onClick={() => setTab("jobs")}>Job moderation</button>
        <button className={`admin-tab${tab === "sources" ? " active" : ""}`} onClick={() => setTab("sources")}>Sources</button>
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
                <option value="pending">Pending</option>
                <option value="active">Active</option>
                <option value="rejected">Rejected</option>
                <option value="expired">Expired</option>
                <option value="">All</option>
              </select>
            </div>
            <div className="admin-filter-field">
              <label>Category</label>
              <select value={jobCategoryFilter} onChange={(e) => { setJobCategoryFilter(e.target.value); loadJobs(jobStatusFilter, e.target.value, jobLocationFilter); }}>
                <option value="">All categories</option>
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
            <button className="admin-filter-clear" onClick={clearJobFilters}>Clear filters</button>
          </div>

          {loading ? (
            <div className="admin-loading">Loading…</div>
          ) : (
            <div className="admin-table-card">
              <table className="admin-table">
                <thead><tr><th>Title</th><th>Company</th><th>Location</th><th>Category</th><th>Status</th><th>Actions</th></tr></thead>
                <tbody>
                  {jobs.map((job) => (
                    <tr key={job.id}>
                      <td className="admin-table-primary">{job.title}</td>
                      <td>{job.company}</td>
                      <td>{job.location || "—"}</td>
                      <td>{job.category || "—"}</td>
                      <td><StatusBadge status={job.status} /></td>
                      <td>
                        {job.status === "pending" && (
                          <div className="admin-row-actions">
                            <button className="btn btn-primary btn-sm" onClick={() => moderate(job.id, "active")}>Approve</button>
                            <button className="btn btn-danger btn-sm" onClick={() => moderate(job.id, "rejected")}>Reject</button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                  {!jobs.length && <tr><td colSpan={6} className="admin-table-empty">No jobs match these filters.</td></tr>}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {loading && tab !== "jobs" && <div className="admin-loading">Loading…</div>}

      {!loading && tab === "sources" && (
        <div className="admin-section">
          <div className="admin-toolbar">
            <button className="btn btn-primary btn-sm" onClick={syncAndRunGreenhouse} disabled={loading}>
              {loading ? "Queueing…" : "Sync + queue Greenhouse"}
            </button>
          </div>
          <div className="admin-automation-card">
            <div>
              <strong>Daily Greenhouse automation</strong>
              <p>Queues configured Greenhouse sources every day at <b>{automation?.schedule_time || "—"}</b> ({automation?.timezone || "—"}). The worker then processes them in the background. Apify and manual runs are unchanged.</p>
              {automation?.last_completed_at && <small>Last scheduler pass: {new Date(automation.last_completed_at).toLocaleString()} · {automation.last_queued_count} source(s) queued</small>}
              {automation?.last_error && <small className="admin-error-text">Last scheduler error: {automation.last_error}</small>}
            </div>
            <label className="switch" title="Enable or disable daily Greenhouse automation">
              <input type="checkbox" checked={automation?.enabled || false} disabled={!automation} onChange={toggleAutomation} />
              <span className="slider" />
            </label>
          </div>
          <h4>Configured sources</h4>
          <div className="admin-table-card">
            <table className="admin-table">
              <thead><tr><th>Name</th><th>Type</th><th>Status</th><th>Last run</th><th>Actions</th></tr></thead>
              <tbody>
                {sources.map((source) => (
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
                {!sources.length && <tr><td colSpan={5} className="admin-table-empty">No sources configured yet.</td></tr>}
              </tbody>
            </table>
          </div>
          <h4>Greenhouse company registry</h4>
          <div className="admin-table-card">
            <table className="admin-table">
              <thead><tr><th>Company</th><th>Status</th><th>Total jobs</th><th>Tamil Nadu</th><th>Last error</th></tr></thead>
              <tbody>
                {companies.map((company) => (
                  <tr key={company.board_id}>
                    <td className="admin-table-primary">{company.name}</td>
                    <td><StatusBadge status={company.status} /></td>
                    <td>{company.total_jobs}</td>
                    <td>{company.tn_job_count}</td>
                    <td>{company.last_error || "—"}</td>
                  </tr>
                ))}
                {!companies.length && <tr><td colSpan={5} className="admin-table-empty">No Greenhouse companies configured.</td></tr>}
              </tbody>
            </table>
          </div>

          <h4>Job boards (Apify — manual only, never scheduled)</h4>
          <div className="admin-table-card">
            <table className="admin-table">
              <thead><tr><th>Platform</th><th>Status</th><th>Jobs fetched</th><th>Last run</th><th>Last error</th><th>Actions</th></tr></thead>
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

          <h4>Recent ingestion runs</h4>
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
              <thead><tr><th>User</th><th>Plan</th><th>Profile complete</th><th>Joined</th><th>Actions</th></tr></thead>
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
