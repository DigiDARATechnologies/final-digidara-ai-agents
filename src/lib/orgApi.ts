/** Organizations as a SaaS product: platform-created organizations, class
 * join codes, and the organization admin's analytics and drill-down
 * (orchestrator app/organizations: service, classes, insights). */
import { sessionToken } from "./session";
import type { Band, LevelId, LearnerProfile, AgentLevel, OrgMember } from "./learnerApi";

const RAW_BASE = import.meta.env.VITE_GATEWAY_API_URL !== undefined ? import.meta.env.VITE_GATEWAY_API_URL : "http://127.0.0.1:8100";
const BASE = RAW_BASE.endsWith("/") ? RAW_BASE.slice(0, -1) : RAW_BASE;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${sessionToken() || ""}`, ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : Array.isArray(body.detail) ? body.detail[0]?.msg : null;
    throw new Error(detail || "Something went wrong. Please try again.");
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

const json = (method: string, body?: unknown): RequestInit => ({ method, body: body === undefined ? undefined : JSON.stringify(body) });

export type ClassKind = "department" | "year" | "section";
export const CLASS_KINDS: ClassKind[] = ["department", "year", "section"];
export const CLASS_LABELS: Record<ClassKind, string> = { department: "Department", year: "Year", section: "Section" };
export type ClassOptions = Record<ClassKind, string[]>;
export type ClassFields = Partial<Record<ClassKind, string | null>>;

export interface JoinPreview {
  organization: { name: string; kind: string };
  code: { label: string } & ClassFields;
  options: ClassOptions;
}

export interface JoinCode {
  id: string;
  code: string;
  label: string;
  department: string | null;
  year: string | null;
  section: string | null;
  active: boolean;
  members: number;
  created_at: string | null;
}

export interface OrgFilters {
  department?: string;
  year?: string;
  section?: string;
  code_id?: string;
  band?: Band;
  agent?: string;
  level?: LevelId;
  status?: "active" | "inactive" | "not_signed_in";
  search?: string;
}

export interface LearnerBrief {
  member_id: string;
  name: string;
  email: string;
  department: string | null;
  year: string | null;
  section: string | null;
  readiness: number | null;
  last_active_at: string | null;
}

export interface GroupStat {
  name: string;
  learners: number;
  average_readiness: number | null;
  bands: Partial<Record<Band, number>>;
}

export interface OrgAnalytics {
  totals: { learners: number; sharing: number; signed_in: number; active_7d: number; inactive_14d: number; average_readiness: number | null };
  bands: Partial<Record<Band, number>>;
  levels: Record<string, Record<LevelId, number>>;
  breakdown: Record<ClassKind, GroupStat[]>;
  usage_30d: Record<string, number>;
  active_trend: { date: string; active_learners: number }[];
  top: LearnerBrief[];
  needs_attention: LearnerBrief[];
  inactive: LearnerBrief[];
  band_labels: Record<string, string>;
  level_labels: Record<LevelId, string>;
  agent_labels: Record<string, string>;
}

export interface MemberArea {
  score: number | null;
  status: string;
  level: LevelId;
  level_progress: number | null;
  level_scores: Partial<Record<LevelId, number>>;
  levels_completed: LevelId[];
  quality_score: number | null;
  /** false: no levels (Resume); `score` is its own result. */
  leveled?: boolean;
}

export interface MemberDetail {
  member: { member_id: string; user_id: string; name: string; email: string; mobile: string; external_id: string | null; joined_at: string | null } & ClassFields;
  profile: LearnerProfile;
  levels: AgentLevel[];
  role_history: { role: string; skills?: string[] }[];
  readiness: null | { overall: number | null; band: Band; band_label: string; computed_at: string; areas: Record<string, MemberArea>; next_steps: string[] };
  readiness_history: { overall: number | null; band: Band; computed_at: string }[];
  activity: { agent_name: string; requests: number; last_at: string | null }[];
  conversations: { id: string; agent_id: string; title: string; messages: number; updated_at: string | null }[];
  memories: { text: string; kind?: string; created_at?: string }[];
  career_plan: { headline?: string; summary?: string } | null;
}

export interface Transcript {
  id: string;
  agent_id: string;
  title: string;
  messages: { role: string; content: string; time: string; created_at: string | null }[];
}

export interface AccessEntry { viewer: string; subject: string; action: string; target: string; at: string | null }

export interface PlatformOrg {
  id: string;
  name: string;
  kind: string;
  join_code?: string;
  member_limit: number;
  member_count: number | null;
  status: "active" | "suspended";
  created_at: string | null;
  active_codes: number;
  admins: { name: string; email: string }[];
}

export interface PlatformCreateResult {
  organization: PlatformOrg;
  admin: { name: string; email: string; status: "created" | "attached"; temporary_password: string | null };
}

function query(filters: OrgFilters): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) if (value) params.set(key, String(value));
  const text = params.toString();
  return text ? `?${text}` : "";
}

export const previewJoinCode = (code: string) => request<JoinPreview>(`/organizations/join-code/${encodeURIComponent(code.trim().toUpperCase())}`);
export const joinWithClass = (code: string, fields: ClassFields) =>
  request<{ membership: unknown; pending?: PendingRequest | null } & Record<string, unknown>>("/organizations/join", json("POST", { join_code: code.trim(), ...fields }));

export const fetchCodes = (orgId: string) => request<JoinCode[]>(`/organizations/${orgId}/codes`);
export const createCode = (orgId: string, body: { label?: string } & ClassFields) => request<JoinCode>(`/organizations/${orgId}/codes`, json("POST", body));
export const setCodeActive = (orgId: string, codeId: string, active: boolean) =>
  request<JoinCode>(`/organizations/${orgId}/codes/${codeId}`, json("PATCH", { active }));
export const fetchOptions = (orgId: string) => request<ClassOptions>(`/organizations/${orgId}/options`);
export const addOption = (orgId: string, kind: ClassKind, value: string) => request<ClassOptions>(`/organizations/${orgId}/options`, json("POST", { kind, value }));

export const fetchAnalytics = (orgId: string, filters: OrgFilters) => request<OrgAnalytics>(`/organizations/${orgId}/analytics${query(filters)}`);
export const fetchFilteredMembers = (orgId: string, filters: OrgFilters) => request<OrgMember[]>(`/organizations/${orgId}/members${query(filters)}`);
export const fetchMemberDetail = (orgId: string, memberId: string) => request<MemberDetail>(`/organizations/${orgId}/members/${memberId}/detail`);
export const fetchMemberConversation = (orgId: string, memberId: string, conversationId: string) =>
  request<Transcript>(`/organizations/${orgId}/members/${memberId}/conversations/${encodeURIComponent(conversationId)}`);
export const fetchAccessLog = (orgId: string) => request<AccessEntry[]>(`/organizations/${orgId}/access-log`);
export const fetchMyAccessLog = () => request<AccessEntry[]>("/organizations/me/access-log");
export const updateMemberClass = (orgId: string, memberId: string, fields: ClassFields) =>
  request<void>(`/organizations/${orgId}/members/${memberId}`, json("PATCH", fields));

export const fetchPlatformOrgs = () => request<PlatformOrg[]>("/organizations/all");
export const platformCreateOrg = (body: { name: string; kind: string; admin_name: string; admin_email: string; member_limit: number }) =>
  request<PlatformCreateResult>("/organizations/platform", json("POST", body));
export const platformUpdateOrg = (orgId: string, body: { status: "active" | "suspended"; member_limit?: number }) =>
  request<PlatformOrg>(`/organizations/platform/${orgId}`, json("PATCH", body));

export interface AssistantTurn { role: "user" | "assistant"; content: string; actions: string[]; created_at: string | null }

export const askAssistant = (orgId: string, message: string, filters: OrgFilters) =>
  request<{ reply: string; actions: string[]; tokens: number }>(`/organizations/${orgId}/assistant`, json("POST", {
    message,
    filters: Object.fromEntries(Object.entries(filters).filter(([key, value]) => value && ["department", "year", "section", "code_id", "band", "status"].includes(key))),
  }));
export const fetchAssistantHistory = (orgId: string) => request<AssistantTurn[]>(`/organizations/${orgId}/assistant/history`);
export const clearAssistant = (orgId: string) => request<void>(`/organizations/${orgId}/assistant/history`, json("DELETE"));

/** A learner's own request to join, waiting for staff approval. */
export interface PendingRequest { id: string; organization: { id: string; name: string } | null; requested_at: string | null }
export const fetchMyJoinRequest = () => request<{ pending: PendingRequest | null }>("/organizations/me/request");
export const cancelMyJoinRequest = () => request<void>("/organizations/me/request", json("DELETE"));

export interface StaffLogin { member_id: string; name: string; email: string; role: "owner" | "admin" | "staff"; has_signed_in: boolean }
export interface AddStaffResult { name: string; email: string; status: "created" | "attached" | "made_staff"; temporary_password: string | null }
export const fetchStaff = (orgId: string) => request<StaffLogin[]>(`/organizations/${orgId}/staff`);
export const addStaff = (orgId: string, body: { name: string; email: string }) =>
  request<AddStaffResult>(`/organizations/${orgId}/staff`, json("POST", body));

/** One student on the uploaded list and where they stand. */
export interface RosterEntry {
  id: string; name: string; email: string; mobile: string;
  status: "joined" | "waiting" | "not_signed_up" | "other_organization"; added_at: string | null;
}
export interface RosterUploadResult {
  added: number; updated: number; joined: number; approved: number; invalid_count: number;
  invalid: { row: number; email: string; reason: string }[];
}
export interface JoinRequest {
  id: string; name: string; email: string; join_code: string | null; requested_at: string | null;
  department: string | null; year: string | null; section: string | null;
}
export const fetchRoster = (orgId: string) => request<RosterEntry[]>(`/organizations/${orgId}/roster`);
export const removeRosterEntry = (orgId: string, entryId: string) => request<void>(`/organizations/${orgId}/roster/${entryId}`, json("DELETE"));
export async function uploadRoster(orgId: string, file: File): Promise<RosterUploadResult> {
  const form = new FormData();
  form.append("file", file);
  // No Content-Type: the browser sets the multipart boundary itself.
  const response = await fetch(`${BASE}/organizations/${orgId}/roster/upload`, {
    method: "POST", body: form, headers: { Authorization: `Bearer ${sessionToken() || ""}` },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : "The file could not be uploaded. Please try again.");
  }
  return response.json();
}
export const fetchJoinRequests = (orgId: string) => request<JoinRequest[]>(`/organizations/${orgId}/requests`);
export const decideJoinRequest = (orgId: string, requestId: string, approve: boolean) =>
  request<void>(`/organizations/${orgId}/requests/${requestId}`, json("POST", { approve }));
