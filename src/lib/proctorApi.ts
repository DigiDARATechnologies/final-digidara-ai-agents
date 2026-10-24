/** Proctoring and assessment links (orchestrator app/proctoring). */
import { sessionToken } from "./session";

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
  return response.json();
}

const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

export type ProctoredAgent = "mock_interview_agent" | "capstone_project_agent";

export interface ProctorSettings {
  tab: boolean;
  fullscreen: boolean;
  copy_paste: boolean;
  webcam: boolean;
  face: boolean;
  max_warnings: number;
}

export interface ProctorState {
  id: string;
  agent_name: string;
  ref: string;
  assessment_id: string | null;
  settings: ProctorSettings;
  status: "active" | "completed" | "terminated";
  warnings: number;
  max_warnings: number;
  warnings_left: number;
  integrity: number;
  terminated: boolean;
}

export type ProctorEventKind = "focus_lost" | "fullscreen_exit" | "copy" | "cut" | "paste" | "context_menu" | "camera_off" | "camera_blocked";

export interface AssessmentConfig {
  round_type: "technical" | "hr";
  role_name: string;
  subject: string;
  num_questions: 5 | 10 | 15;
  level: "beginner" | "medium" | "hard" | "professional";
  level_label?: string;
}

export interface AssessmentPreview {
  title: string;
  kind: string;
  organization: string;
  config: AssessmentConfig;
  proctoring: ProctorSettings;
  opens_at: string | null;
  closes_at: string | null;
  window: "open" | "not_open" | "closed" | "inactive";
  can_start: boolean;
  reason: string;
  attempt: {
    session_id: string; status: string; integrity: number; warnings: number; result: ProctorResult | null;
    started_at: string | null; ended_at: string | null;
  } | null;
}

export interface ProctorResult {
  score?: number | null;
  max?: number | null;
  overall?: number | null;
  ended_early?: boolean;
  label?: string | null;
  passed?: boolean;
}

export interface Assessment {
  id: string;
  title: string;
  kind: string;
  config: AssessmentConfig;
  proctoring: ProctorSettings;
  path: string;
  opens_at: string | null;
  closes_at: string | null;
  members_only: boolean;
  active: boolean;
  attempts: number;
  created_at: string | null;
}

export interface ProctorSummary {
  session_id: string;
  user_id: string;
  name: string;
  email: string;
  agent_name: string;
  ref: string;
  status: "active" | "completed" | "terminated";
  integrity: number;
  warnings: number;
  result: ProctorResult | null;
  started_at: string | null;
  ended_at: string | null;
  assessment_id: string | null;
}

export interface ProctorDetail extends ProctorSummary {
  settings: ProctorSettings;
  events: { kind: string; detail: string; penalty: number; at: string | null }[];
  snapshots: { id: string; faces: number | null; note: string; at: string | null }[];
  retention_days: number;
}

// Learner
export const startProctoring = (agentName: ProctoredAgent, ref: string) =>
  request<ProctorState>("/proctoring/sessions", post({ agent_name: agentName, ref, consent: true }));
export const sendProctorEvents = (sessionId: string, events: { kind: ProctorEventKind; detail?: string }[]) =>
  request<ProctorState>(`/proctoring/sessions/${sessionId}/events`, post({ events }));
export const sendProctorSnapshot = (sessionId: string, image: string) =>
  request<ProctorState>(`/proctoring/sessions/${sessionId}/snapshots`, post({ image }));
export const fetchProctorState = (sessionId: string) => request<ProctorState>(`/proctoring/sessions/${sessionId}`);
export const endProctoring = (sessionId: string) => request<ProctorState>(`/proctoring/sessions/${sessionId}/end`, post({}));
export const previewAssessment = (token: string) => request<AssessmentPreview>(`/assessments/${encodeURIComponent(token)}`);
export const startAssessment = (token: string) =>
  request<ProctorState & { assessment: { title: string; config: AssessmentConfig } }>(`/assessments/${encodeURIComponent(token)}/start`, post({ consent: true }));

// Organization admins
export const fetchAssessments = (orgId: string) => request<Assessment[]>(`/organizations/${orgId}/assessments`);
export const createAssessment = (orgId: string, body: {
  title: string; config: Omit<AssessmentConfig, "level_label">; proctoring: ProctorSettings;
  opens_at: string | null; closes_at: string | null; members_only: boolean;
}) => request<Assessment>(`/organizations/${orgId}/assessments`, post(body));
export const setAssessmentActive = (orgId: string, assessmentId: string, active: boolean) =>
  request<Assessment>(`/organizations/${orgId}/assessments/${assessmentId}`, { method: "PATCH", body: JSON.stringify({ active }) });
export const fetchAssessmentAttempts = (orgId: string, assessmentId: string) =>
  request<ProctorSummary[]>(`/organizations/${orgId}/assessments/${assessmentId}/attempts`);
export const fetchMemberProctoring = (orgId: string, memberId: string) =>
  request<ProctorSummary[]>(`/organizations/${orgId}/members/${memberId}/proctoring`);
export const fetchProctorDetail = (orgId: string, sessionId: string) =>
  request<ProctorDetail>(`/organizations/${orgId}/proctoring/${sessionId}`);

/** A webcam still as an object URL (the request needs the sign-in token, so
 * an <img src> cannot fetch it directly). */
export async function fetchSnapshotUrl(orgId: string, sessionId: string, snapshotId: string): Promise<string> {
  const response = await fetch(`${BASE}/organizations/${orgId}/proctoring/${sessionId}/snapshots/${snapshotId}`, {
    headers: { Authorization: `Bearer ${sessionToken() || ""}` },
  });
  if (!response.ok) throw new Error("This snapshot is no longer available.");
  return URL.createObjectURL(await response.blob());
}
