/** Phase 2: learner profile, per-agent levels, job readiness and
 * organizations (orchestrator app/learner, app/organizations). */
const RAW_BASE = import.meta.env.VITE_GATEWAY_API_URL !== undefined ? import.meta.env.VITE_GATEWAY_API_URL : "http://127.0.0.1:8100";
const BASE = RAW_BASE.endsWith("/") ? RAW_BASE.slice(0, -1) : RAW_BASE;

export type LevelId = "beginner" | "medium" | "hard" | "professional";
export const LEVEL_IDS: LevelId[] = ["beginner", "medium", "hard", "professional"];
export const LEVEL_LABELS: Record<LevelId, string> = {
  beginner: "Beginner",
  medium: "Medium",
  hard: "Hard",
  professional: "Professional",
};

export interface LearnerProfile {
  target_role: string;
  degree: string;
  skills: string[];
  experience: "fresher" | "experienced";
  onboarding_completed: boolean;
  onboarding_completed_at: string | null;
}

export interface AgentLevel {
  agent_name: string;
  agent_label: string;
  level: LevelId;
  source: "default" | "self" | "organization" | "readiness";
  updated_at: string | null;
}

export interface Organization {
  id: string;
  name: string;
  kind: string;
  join_code?: string;
  member_limit: number;
  member_count: number | null;
  created_at: string | null;
}

export interface Membership {
  organization: Organization;
  role: "owner" | "admin" | "member";
  member_id: string;
  external_id: string | null;
  progress_shared: boolean;
}

export interface LearnerSummary {
  profile: LearnerProfile;
  levels: AgentLevel[];
  level_choices: { id: LevelId; label: string }[];
  consent_required: boolean;
  membership: Membership | null;
}

export type AreaStatus = "assessed" | "not_started" | "unavailable";

export interface ReadinessArea {
  agent_name: string;
  label: string;
  weight: number;
  level: LevelId;
  status: AreaStatus;
  reason?: string;
  score: number | null;
  activity_count: number;
  last_activity_at: string | null;
  strengths: string[];
  gaps: string[];
  metrics: Record<string, string | number | boolean | null>;
  suggested_level: LevelId | null;
}

export type Band = "not_started" | "not_ready" | "developing" | "almost_ready" | "job_ready";

/** Colour tone per band, used by the readiness ring and badges. */
export const BAND_TONE: Record<Band, string> = {
  not_started: "muted", not_ready: "low", developing: "mid", almost_ready: "good", job_ready: "top",
};

export interface Readiness {
  overall: number | null;
  band: Band;
  band_label: string;
  coverage: { assessed: number; total: number };
  areas: ReadinessArea[];
  next_steps: string[];
  profile: LearnerProfile;
  computed_at: string;
  cached?: boolean;
}

export interface MemberReadiness {
  overall: number | null;
  band: Band;
  band_label: string;
  computed_at: string;
  areas: Record<string, { score: number | null; status: AreaStatus; level: LevelId }>;
}

export interface OrgMember {
  member_id: string;
  user_id: string;
  name: string;
  email: string;
  role: Membership["role"];
  external_id: string | null;
  joined_at: string | null;
  progress_shared: boolean;
  has_signed_in: boolean;
  readiness?: MemberReadiness | null;
  levels?: Record<string, LevelId>;
  profile?: LearnerProfile;
}

export interface OrgSummary {
  members: number;
  sharing: number;
  signed_in: number;
  average_readiness: number | null;
  bands: Partial<Record<Band, number>>;
  levels: Record<string, Record<LevelId, number>>;
  band_labels: Record<Band, string>;
  level_labels: Record<LevelId, string>;
  agent_labels: Record<string, string>;
}

export interface AddMemberResult {
  email: string;
  name?: string;
  status: "created" | "attached" | "invalid_email" | "limit_reached" | "already_in_organization" | "in_another_organization";
  temporary_password?: string | null;
}

function token() {
  return localStorage.getItem("digidara_token") || "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token()}`, ...init?.headers },
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

export const fetchLearnerSummary = () => request<LearnerSummary>("/learner/profile");
export const saveLearnerProfile = (profile: Pick<LearnerProfile, "target_role" | "degree" | "skills" | "experience">) =>
  request<LearnerSummary>("/learner/profile", json("PUT", profile));
export const setMyLevel = (agentName: string, level: LevelId) =>
  request<AgentLevel>(`/learner/levels/${encodeURIComponent(agentName)}`, json("PUT", { level }));
export const acceptConsent = (shareProgress: boolean | null) =>
  request<LearnerSummary>("/learner/consent", json("POST", { consent: true, share_progress: shareProgress }));
export const fetchReadiness = (refresh = false) => request<Readiness>(`/learner/readiness${refresh ? "?refresh=true" : ""}`);
export const fetchReadinessHistory = () =>
  request<{ overall: number | null; band: Band; computed_at: string }[]>("/learner/readiness/history");

export const createOrganization = (name: string, kind: string) => request<Membership>("/organizations", json("POST", { name, kind }));
export const joinOrganization = (joinCode: string, shareProgress: boolean) =>
  request<Membership>("/organizations/join", json("POST", { join_code: joinCode, share_progress: shareProgress }));
export const setProgressSharing = (share: boolean) => request<Membership>("/organizations/me/sharing", json("PUT", { share }));
export const leaveOrganization = () => request<void>("/organizations/me", json("DELETE"));
export const fetchOrgSummary = (orgId: string) => request<OrgSummary>(`/organizations/${orgId}/summary`);
export const fetchOrgMembers = (orgId: string) => request<OrgMember[]>(`/organizations/${orgId}/members`);
export const addOrgMembers = (orgId: string, members: { name: string; email: string; external_id?: string }[]) =>
  request<{ results: AddMemberResult[] }>(`/organizations/${orgId}/members`, json("POST", { members }));
export const updateOrgMember = (orgId: string, memberId: string, change: { role?: Membership["role"]; external_id?: string }) =>
  request<void>(`/organizations/${orgId}/members/${memberId}`, json("PATCH", change));
export const removeOrgMember = (orgId: string, memberId: string) => request<void>(`/organizations/${orgId}/members/${memberId}`, json("DELETE"));
export const setMemberLevel = (orgId: string, memberId: string, agentName: string, level: LevelId) =>
  request<AgentLevel>(`/organizations/${orgId}/members/${memberId}/levels/${encodeURIComponent(agentName)}`, json("PUT", { level }));
export const refreshMemberReadiness = (orgId: string, memberId: string) =>
  request<Readiness>(`/organizations/${orgId}/members/${memberId}/readiness`, json("POST"));
export const rotateJoinCode = (orgId: string) => request<Membership>(`/organizations/${orgId}/join-code`, json("POST"));
