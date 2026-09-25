import { gatewayInvokeUrl, invokeAgent } from "./gatewayClient";

const INVOKE_URL = gatewayInvokeUrl(import.meta.env.VITE_JOB_AGENT_NAME, "job_agent");
function invoke<T>(action: string, payload: Record<string, unknown> = {}): Promise<T> {
  return invokeAgent<T>(INVOKE_URL, action, payload);
}

// Unlike Aptitude/CodeForge/Communication, this agent needs no session token
// in the payload — the orchestrator gateway itself verifies the platform
// login and forwards a signed identity header directly to the agent (see
// agents/job_agent/auth.py), so every call below just needs the platform
// bearer token gatewayClient.ts already attaches from localStorage.

export interface JobFetchProfile {
  user_id: string;
  full_name: string | null;
  skills: string[];
  preferred_titles: string[];
  preferred_locations: string[];
  preferred_work_mode: string;
  experience_years: number;
  resume_url: string;
  resume_original_name: string | null;
  profile_completed: boolean;
  plan_tier: string;
}

export interface JobFeedItem {
  id: number;
  title: string;
  company: string;
  location: string | null;
  work_mode: string | null;
  employment_type: string | null;
  apply_url: string;
  description: string | null;
  skills: string[];
  match_score: number;
  match_reasons: string[];
  is_saved: number;
  application_status: string | null;
  trust_score?: number;
  trust_badge?: string;
  is_verified?: boolean;
  seniority_tier?: "entry" | "growth" | "senior";
  salary_text?: string | null;
  experience_min?: number | null;
  experience_max?: number | null;
}

export interface SavedJobItem {
  id: number;
  title: string;
  company: string;
  location: string | null;
  work_mode: string | null;
  apply_url: string;
  status: string;
  expires_at: string | null;
  application_status: string | null;
  updated_at: string;
}

export interface AppliedJobItem {
  id: number;
  title: string;
  company: string;
  location: string | null;
  apply_url: string;
  application_status: string;
  applied_at: string | null;
  updated_at: string;
}

export interface HiddenJobItem {
  id: number;
  title: string;
  company: string;
  location: string | null;
  work_mode: string | null;
  apply_url: string;
  status: string;
  updated_at: string;
}

export function checkJobFetchHealth() {
  return invoke<{ status: string }>("health").then((result) => result.status === "ok");
}

export function ensureJobFetchProfile() {
  return invoke<{ user_id: string; profile_completed: boolean; plan_tier: string }>("ensure_profile");
}

export function getJobFetchProfile() {
  return invoke<{ profile: JobFetchProfile }>("get_profile").then((result) => result.profile);
}

export function updateJobFetchProfile(profile: {
  full_name?: string;
  skills: string[];
  preferred_titles: string[];
  preferred_locations: string[];
  preferred_work_mode?: string;
  experience_years?: number;
  resume_url?: string;
}) {
  return invoke<{ message: string; profile_completed: boolean }>("update_profile", profile);
}

export interface JobAgentChatResponse {
  reply: string;
  show_jobs?: boolean;
  updated_profile: {
    skills: string[];
    preferred_locations: string[];
    preferred_titles: string[];
    preferred_work_mode: string;
    experience_years: number;
    changed_fields: string[];
  };
  suggested_actions: Array<{ label: string; value: string }>;
  matched_jobs: JobFeedItem[];
}

export function chatWithJobAgent(
  message: string,
  history: Array<{ role: string; content: string }> = [],
  selectedJobId?: number,
) {
  return invoke<JobAgentChatResponse>("chat", {
    message,
    history,
    selected_job_id: selectedJobId,
  });
}

/** Resume upload — the one job_agent action that isn't plain JSON, so it
 * bypasses gatewayClient.ts's invoke() and posts multipart directly, the
 * same shape resumeBuilderApi.ts's upload uses. The platform bearer token
 * still has to be attached by hand here since this doesn't go through
 * invokeAgent(). */
export async function uploadJobFetchResume(file: File): Promise<{ message: string; filename: string }> {
  const form = new FormData();
  form.append("action", "upload_resume");
  form.append("payload", "{}");
  form.append("file", file);
  const token = localStorage.getItem("digidara_token");
  const response = await fetch(INVOKE_URL, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || body.message || response.statusText);
  return body;
}

/** Download the authenticated user's stored resume file blob. */
export async function downloadJobFetchResume(): Promise<Blob> {
  const token = localStorage.getItem("digidara_token");
  const response = await fetch(INVOKE_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ action: "download_resume", payload: {} }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || body.message || "Failed to download resume");
  }
  return response.blob();
}


export function getJobFeed(filters: { q?: string; location?: string; work_mode?: string; category?: string; saved?: boolean } = {}) {
  return invoke<{ jobs: JobFeedItem[]; total: number; returned: number; plan_tier: string; limit: number }>(
    "get_feed",
    filters,
  );
}

export function jobFetchAction(jobId: number, action: "save" | "unsave" | "hide" | "unhide" | "apply") {
  return invoke<{ message: string; action: string }>("job_action", { job_id: jobId, action });
}

export function updateJobApplicationStatus(
  jobId: number,
  status: "applied" | "screening" | "interview" | "offer" | "rejected" | "withdrawn" | string,
) {
  return invoke<{ message: string; job_id: number; application_status: string }>("update_application_status", {
    job_id: jobId,
    status,
  });
}

export function getJobFetchApplications() {
  return invoke<{ applications: AppliedJobItem[] }>("get_applications");
}

export function getSavedJobFetchJobs() {
  return invoke<{ jobs: SavedJobItem[] }>("get_saved_jobs");
}

export function getHiddenJobFetchJobs() {
  return invoke<{ jobs: HiddenJobItem[] }>("get_hidden_jobs");
}

// --- Admin (gated server-side on the gateway's verified
// X-Digidara-Is-Admin header — see agents/job_agent/auth.py) ---

export function adminListUsers() {
  return invoke<{ users: Array<Record<string, any>> }>("admin_list_users");
}

export function adminUpdatePlan(userId: string, planTier: "free" | "pro") {
  return invoke<{ message: string; plan_tier: string }>("admin_update_plan", { user_id: userId, plan_tier: planTier });
}

export interface PageInfo {
  total: number;
  limit: number;
  offset: number;
}

export function adminListJobs(
  filters: { status?: string; category?: string; location?: string; limit?: number; offset?: number } = {},
) {
  const payload: Record<string, string | number> = {};
  if (filters.status) payload.status = filters.status;
  if (filters.category) payload.category = filters.category;
  if (filters.location) payload.location = filters.location;
  if (filters.limit != null) payload.limit = filters.limit;
  if (filters.offset != null) payload.offset = filters.offset;
  return invoke<{ jobs: Array<Record<string, any>> } & PageInfo>("admin_list_jobs", payload);
}

export function adminListCategories() {
  return invoke<{ categories: Array<{ id: string; label: string }> }>("admin_list_categories");
}

export function adminUpdateJobStatus(jobId: number, status: "pending" | "active" | "rejected" | "expired") {
  return invoke<{ message: string; status: string }>("admin_update_job_status", { job_id: jobId, status });
}

export function adminListSources(page: { limit?: number; offset?: number } = {}) {
  const payload: Record<string, number> = {};
  if (page.limit != null) payload.limit = page.limit;
  if (page.offset != null) payload.offset = page.offset;
  return invoke<{ sources: Array<Record<string, any>> } & PageInfo>("admin_list_sources", payload);
}

export interface JobAutomationSettings {
  enabled: boolean;
  schedule_time: string;
  timezone: string;
  last_scheduled_date: string | null;
  last_started_at: string | null;
  last_completed_at: string | null;
  last_queued_count: number;
  last_error: string | null;
}

export function adminGetAutomation() {
  return invoke<{ automation: JobAutomationSettings }>("admin_get_automation");
}

export function adminUpdateAutomation(enabled: boolean) {
  return invoke<{ automation: JobAutomationSettings }>("admin_update_automation", { enabled });
}

export function adminRunSource(sourceId: number) {
  return invoke<{ message: string; run_id: number; queued: boolean }>("admin_run_source", { source_id: sourceId });
}

export interface IngestionRun {
  id: number;
  source_id: number;
  source_name: string;
  status: "queued" | "running" | "completed" | "failed";
  fetched_count: number;
  inserted_count: number;
  updated_count: number;
  rejected_count: number;
  expired_count: number;
  error_message: string | null;
  queued_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export function adminListRuns(page: { limit?: number; offset?: number } = {}) {
  const payload: Record<string, number> = {};
  if (page.limit != null) payload.limit = page.limit;
  if (page.offset != null) payload.offset = page.offset;
  return invoke<{ runs: IngestionRun[] } & PageInfo>("admin_list_runs", payload);
}

export interface QueueCollectionResult {
  message: string;
  ready: boolean;
  source_count: number;
  queued_count: number;
  already_queued_count: number;
  queued: Array<{ source_id: number; source_name: string; run_id: number }>;
  already_queued: Array<{ source_id: number; source_name: string; run_id: number }>;
}

export function adminGreenhouseCompanies() {
  return invoke<{ companies: Array<Record<string, any>> }>("admin_greenhouse_companies");
}

export function adminGreenhouseSync() {
  return invoke<{ message: string; companies: number }>("admin_greenhouse_sync");
}

export function adminGreenhouseRun() {
  return invoke<QueueCollectionResult>("admin_greenhouse_run");
}

export function adminApifyStatus() {
  return invoke<{ ready: boolean; reason: string }>("admin_apify_status");
}

export interface ApifyActor {
  platform: string;
  source_id: number | null;
  actor_id: string;
  configured: boolean;
  status: string;
  last_run_at: string | null;
  last_error: string | null;
  last_fetched_count: number | null;
}

export function adminApifyActors() {
  return invoke<{ actors: ApifyActor[] }>("admin_apify_actors");
}

/** Manual only — never scheduled. Omit `platform` to run every enabled actor. */
export function adminApifyRun(platform?: string) {
  return invoke<QueueCollectionResult>("admin_apify_run", platform ? { platform } : {});
}

export function adminTnCoverage() {
  return invoke<Record<string, any>>("admin_tn_coverage");
}

export function adminAdzunaStatus() {
  return invoke<{ ready: boolean; enabled: boolean; configured: boolean; queries_count: number; reason: string }>(
    "admin_adzuna_status"
  );
}

export function adminAdzunaRun() {
  return invoke<QueueCollectionResult>("admin_adzuna_run");
}

export function adminJSearchStatus() {
  return invoke<{ ready: boolean; enabled: boolean; configured: boolean; queries_count: number; reason: string }>(
    "admin_jsearch_status"
  );
}

export function adminJSearchRun() {
  return invoke<QueueCollectionResult>("admin_jsearch_run");
}

export interface JobTokenSettings {
  free_daily_feed_limit: number;
  free_daily_chat_turns: number;
  tokens_per_extra_feed: number;
  tokens_per_chat_turn: number;
}

export function adminGetTokenSettings() {
  return invoke<{ token_settings: JobTokenSettings }>("admin_get_token_settings");
}

export function adminUpdateTokenSettings(settings: Partial<JobTokenSettings>) {
  return invoke<{ message: string; token_settings: JobTokenSettings }>("admin_update_token_settings", settings);
}

export function adminPruneJobs(maxAgeDays = 30) {
  return invoke<{ message: string; expired_count: number; deleted_count: number }>("admin_prune_jobs", {
    max_age_days: maxAgeDays,
  });
}

