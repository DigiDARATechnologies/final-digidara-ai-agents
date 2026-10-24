/** Knowledge tests (orchestrator app/knowledge): admins build them from
 * documents; learners take them through an assessment link. */
import { sessionToken } from "./session";

const RAW_BASE = import.meta.env.VITE_GATEWAY_API_URL !== undefined ? import.meta.env.VITE_GATEWAY_API_URL : "http://127.0.0.1:8100";
const BASE = RAW_BASE.endsWith("/") ? RAW_BASE.slice(0, -1) : RAW_BASE;

async function failure(response: Response): Promise<Error> {
  const body = await response.json().catch(() => ({}));
  const detail = typeof body.detail === "string" ? body.detail : Array.isArray(body.detail) ? body.detail[0]?.msg : null;
  if (response.status === 413) return new Error("This file is too large to upload.");
  return new Error(detail || "Something went wrong. Please try again.");
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isForm = init?.body instanceof FormData;
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { ...(isForm ? {} : { "Content-Type": "application/json" }), Authorization: `Bearer ${sessionToken() || ""}`, ...init?.headers },
  });
  if (!response.ok) throw await failure(response);
  if (response.status === 204) return undefined as T;
  return response.json();
}

const send = (method: string, body?: unknown): RequestInit => ({ method, body: body === undefined ? undefined : JSON.stringify(body) });

export type QuestionType = "mcq" | "qa" | "mixed";
export const QUESTION_TYPE_LABELS: Record<QuestionType, string> = {
  mcq: "Multiple choice", qa: "Question and answer", mixed: "Both (multiple choice and Q&A)",
};

export interface KnowledgeQuestion {
  id: string;
  position: number;
  qtype: "mcq" | "qa";
  question: string;
  options: string[];
  correct: number | null;
  answer: string;
  explanation: string;
}

export interface KnowledgeDocument { id: string; filename: string; kind: string; chars: number; created_at: string | null }

export interface KnowledgeTest {
  id: string;
  title: string;
  question_type: QuestionType;
  num_questions: number;
  seconds_per_question: number;
  instructions: string;
  status: "draft" | "generating" | "ready" | "failed";
  error: string;
  question_count: number;
  document_count: number;
  locked: boolean;
  created_at: string | null;
  updated_at: string | null;
  documents?: KnowledgeDocument[];
  questions?: KnowledgeQuestion[];
}

export interface UploadResult { filename: string; ok: boolean; message?: string; chars?: number }

export interface LearnerQuestion { id: string; position: number; qtype: "mcq" | "qa"; question: string; options: string[] }

export interface ReportRow {
  number: number;
  qtype: "mcq" | "qa";
  question: string;
  options: string[];
  your_answer: string;
  correct_answer: string;
  verdict: "correct" | "partial" | "wrong" | "ungraded";
  points: number;
  feedback: string;
  explanation: string;
  time_taken: number | null;
  timed_out: boolean;
  answered: boolean;
}

export interface KnowledgeReport {
  title: string;
  organization: string;
  learner: string;
  email: string;
  finished_at: string | null;
  score: number;
  max: number;
  percent: number;
  integrity: number | null;
  proctor_status: string | null;
  summary: string;
  strengths: string[];
  improve: string[];
  rows: ReportRow[];
}

export interface KnowledgeAttempt {
  id: string;
  status: "active" | "completed";
  title: string;
  question_type: QuestionType;
  seconds_per_question: number;
  questions: LearnerQuestion[];
  answered: string[];
  report: KnowledgeReport | null;
}

// Organization admins
const base = (orgId: string) => `/organizations/${orgId}/knowledge-tests`;
export const fetchKnowledgeTests = (orgId: string) => request<KnowledgeTest[]>(base(orgId));
export const fetchKnowledgeTest = (orgId: string, testId: string) => request<KnowledgeTest>(`${base(orgId)}/${testId}`);
export const createKnowledgeTest = (orgId: string, body: {
  title: string; question_type: QuestionType; num_questions: number; seconds_per_question: number; instructions: string;
}) => request<KnowledgeTest>(base(orgId), send("POST", body));
export const updateKnowledgeTest = (orgId: string, testId: string, body: Partial<Pick<KnowledgeTest, "title" | "question_type" | "num_questions" | "seconds_per_question" | "instructions">>) =>
  request<KnowledgeTest>(`${base(orgId)}/${testId}`, send("PATCH", body));
export const deleteKnowledgeTest = (orgId: string, testId: string) => request<void>(`${base(orgId)}/${testId}`, send("DELETE"));
export function uploadKnowledgeDocument(orgId: string, testId: string, file: File) {
  const form = new FormData();
  form.append("files", file);
  return request<{ test: KnowledgeTest; results: UploadResult[] }>(`${base(orgId)}/${testId}/documents`, { method: "POST", body: form });
}
export const deleteKnowledgeDocument = (orgId: string, testId: string, documentId: string) =>
  request<KnowledgeTest>(`${base(orgId)}/${testId}/documents/${documentId}`, send("DELETE"));
export const generateKnowledgeQuestions = (orgId: string, testId: string) => request<KnowledgeTest>(`${base(orgId)}/${testId}/generate`, send("POST"));
export const updateKnowledgeQuestion = (orgId: string, testId: string, questionId: string, body: Partial<Pick<KnowledgeQuestion, "question" | "options" | "correct" | "answer" | "explanation">>) =>
  request<KnowledgeQuestion>(`${base(orgId)}/${testId}/questions/${questionId}`, send("PATCH", body));
export const deleteKnowledgeQuestion = (orgId: string, testId: string, questionId: string) =>
  request<KnowledgeTest>(`${base(orgId)}/${testId}/questions/${questionId}`, send("DELETE"));
export const fetchAdminKnowledgeReport = (orgId: string, sessionId: string) =>
  request<KnowledgeReport>(`/organizations/${orgId}/proctoring/${sessionId}/knowledge-report`);

// Learners
export const startKnowledgeAttempt = (sessionId: string) => request<KnowledgeAttempt>("/knowledge/attempts", send("POST", { session_id: sessionId }));
export const submitKnowledgeAnswer = (attemptId: string, body: { question_id: string; answer: string; time_taken: number; timed_out: boolean }) =>
  request<{ answered: string[] }>(`/knowledge/attempts/${attemptId}/answers`, send("POST", body));
export const finishKnowledgeAttempt = (attemptId: string) => request<KnowledgeAttempt>(`/knowledge/attempts/${attemptId}/finish`, send("POST"));

/** Saves a report PDF (the learner's own, or, with an organization, a learner's). */
export async function downloadKnowledgeReport(path: { attemptId: string } | { orgId: string; sessionId: string }, filename: string): Promise<void> {
  const url = "attemptId" in path
    ? `${BASE}/knowledge/attempts/${path.attemptId}/report.pdf`
    : `${BASE}/organizations/${path.orgId}/proctoring/${path.sessionId}/knowledge-report.pdf`;
  const response = await fetch(url, { headers: { Authorization: `Bearer ${sessionToken() || ""}` } });
  if (!response.ok) throw await failure(response);
  const link = document.createElement("a");
  link.href = URL.createObjectURL(await response.blob());
  link.download = `${filename.replace(/[^\w-]+/g, "_").slice(0, 60) || "test"}_report.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(link.href), 60_000);
}
