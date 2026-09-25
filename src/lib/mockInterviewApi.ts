import { gatewayInvokeUrl, invokeAgent } from "./gatewayClient";

const INVOKE_URL = gatewayInvokeUrl(import.meta.env.VITE_MOCK_INTERVIEW_AGENT_NAME, "mock_interview_agent");
const TIMEOUT_MS = Number(import.meta.env.VITE_MOCK_INTERVIEW_TIMEOUT_MS || 190000);

export interface MockInterviewQuestion {
  active?: boolean;
  interview_id: number;
  question_order: number;
  question: string;
  total_questions?: number;
  round_type?: string;
  interview_mode?: "course" | "custom_topic" | "role" | "weak_topic_practice";
  role_name?: string | null;
  difficulty?: "beginner" | "intermediate" | "advanced";
  resumed_existing?: boolean;
  real_question_index?: number;
  is_followup?: boolean;
}

export interface MockInterviewAnswerResult {
  done?: boolean;
  verdict?: string | null;
  verdict_reason?: string | null;
  question?: string;
  question_order?: number;
  total_questions?: number;
  is_followup?: boolean;
  real_question_index?: number;
  answered_question_verdict?: { verdict?: string | null; reason?: string | null };
}

export interface MockInterviewSummary {
  interview_id?: number;
  total_marks?: number;
  max_marks?: number;
  overall_score?: number | null;
  technical_accuracy?: number | null;
  communication_clarity?: number | null;
  confidence?: number | null;
  strengths?: string;
  weaknesses?: string;
  feedback?: string;
  subject_breakdown?: {
    weak_subjects?: string[];
    strong_subjects?: string[];
    subjects?: Array<{ subject?: string; status?: string; score?: number }>;
  } | null;
  scorecard?: Array<{
    question_number?: number;
    question?: string;
    answer?: string;
    verdict?: string;
    verdict_reason?: string;
    ideal_answer?: string;
  }>;
}

function invoke<T>(action: string, payload: Record<string, unknown>): Promise<T> {
  return invokeAgent<T>(INVOKE_URL, action, payload, 1, TIMEOUT_MS);
}

export async function checkMockInterviewHealth(): Promise<boolean> {
  try { return (await invoke<{ status: string }>("health", {})).status === "ok"; } catch { return false; }
}

export async function ensureMockInterviewSession(userId: string, name: string, email: string) {
  return invoke<{ sessionToken: string; student_id: number }>("ensure_session", { user_id: userId, name, email });
}

export function getActiveMockInterview(sessionToken: string) {
  return invoke<MockInterviewQuestion | { active: false }>("active_interview", { sessionToken });
}

export function startMockInterview(sessionToken: string, input: {
  round_type: "technical" | "hr";
  subject?: string;
  role_name?: string;
  resolved_subjects?: string[];
  difficulty: string;
  interview_mode: "course" | "custom_topic" | "role" | "weak_topic_practice";
  num_questions: 5 | 10 | 15;
}) {
  return invoke<MockInterviewQuestion>("start_interview", { sessionToken, ...input });
}

export function submitMockInterviewAnswer(sessionToken: string, interviewId: number, questionOrder: number, answer: string, timeTakenSec = 0, timedOut = false) {
  return invoke<MockInterviewAnswerResult>("submit_answer", {
    sessionToken, interview_id: interviewId, question_order: questionOrder,
    answer, time_taken_sec: Math.max(0, Math.min(600, Math.round(timeTakenSec))), timed_out: timedOut,
  });
}

export function endMockInterview(sessionToken: string, interviewId: number) {
  return invoke<MockInterviewSummary>("end_interview", { sessionToken, interview_id: interviewId });
}

export function exitMockInterview(sessionToken: string, interviewId: number, questionOrder?: number) {
  return invoke<Record<string, unknown>>("exit_interview", { sessionToken, interview_id: interviewId, ...(questionOrder ? { question_order: questionOrder } : {}) });
}

export async function downloadMockInterviewReport(sessionToken: string, interviewId: number): Promise<void> {
  const report = await invoke<{ content_type: string; filename: string; data: string }>("download_report", {
    sessionToken, interview_id: interviewId,
  });
  if (report.content_type !== "application/pdf" || !report.data) throw new Error("The PDF report is unavailable.");
  const binary = atob(report.data);
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = report.filename || `Interview_Report_${interviewId}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
