import { gatewayInvokeUrl, invokeAgent } from "./gatewayClient";

const INVOKE_URL = gatewayInvokeUrl(import.meta.env.VITE_MOCK_INTERVIEW_AGENT_NAME, "mock_interview_agent");
const TIMEOUT_MS = Number(import.meta.env.VITE_MOCK_INTERVIEW_TIMEOUT_MS || 120000);

export interface MockInterviewQuestion {
  interview_id: number;
  question_order: number;
  question: string;
  total_questions?: number;
  round_type?: string;
  resumed_existing?: boolean;
}

export interface MockInterviewAnswerResult {
  done?: boolean;
  verdict?: string | null;
  verdict_reason?: string | null;
  question?: string;
  question_order?: number;
  total_questions?: number;
}

export interface MockInterviewSummary {
  total_marks?: number;
  max_marks?: number;
  overall_score?: number | null;
  summary?: string;
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

export function startMockInterview(sessionToken: string, input: { round_type: "technical" | "hr"; subject?: string; difficulty: string; interview_mode?: string; num_questions?: number }) {
  return invoke<MockInterviewQuestion>("start_interview", { sessionToken, interview_mode: "custom_topic", num_questions: 5, ...input });
}

export function submitMockInterviewAnswer(sessionToken: string, interviewId: number, questionOrder: number, answer: string) {
  return invoke<MockInterviewAnswerResult>("submit_answer", { sessionToken, interview_id: interviewId, question_order: questionOrder, answer });
}

export function endMockInterview(sessionToken: string, interviewId: number) {
  return invoke<MockInterviewSummary>("end_interview", { sessionToken, interview_id: interviewId });
}

export function exitMockInterview(sessionToken: string, interviewId: number, questionOrder?: number) {
  return invoke<Record<string, unknown>>("exit_interview", { sessionToken, interview_id: interviewId, ...(questionOrder ? { question_order: questionOrder } : {}) });
}
