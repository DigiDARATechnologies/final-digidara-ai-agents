import { gatewayInvokeUrl, invokeAgent } from "./gatewayClient";

const INVOKE_URL = gatewayInvokeUrl(import.meta.env.VITE_APTITUDE_AGENT_NAME, "aptitude_agent");
function invoke<T>(action: string, payload: Record<string, unknown> = {}): Promise<T> { return invokeAgent<T>(INVOKE_URL, action, payload); }

export interface AptitudeQuestion { test_id: string; sequence: number; total_questions: number; category: string; topic: string; topic_is_starred?: boolean; difficulty: string; question: string; options: Record<string, string>; allowed_time_seconds: number; remaining_seconds?: number; deadline_at_ms?: number; hints_remaining: number; }
export interface MixedTestCategory { category_id: string; category_name: string; question_count: number; default_count: number; }
export interface MixedTestConfig { categories: MixedTestCategory[]; total_questions: number; limits: { min_per_category: number; max_per_category: number; max_total: number; }; }
export interface AptitudeAnswerResult { is_correct: boolean; timed_out: boolean; correct_answer: string; explanation: string; complete: boolean; next_sequence: number | null; }
export function checkAptitudeHealth() { return invoke<{ status: string }>("health").then((result) => result.status === "ok"); }
export function ensureAptitudeSession(user: { id: string; name: string; email: string; mobile: string }) { return invoke<{ sessionToken: string; student: { id: string; name: string; email: string; mobile: string } }>("ensure_session", { user_id: user.id, name: user.name, email: user.email, mobile: user.mobile }); }
export function getAptitudeDashboard(sessionToken: string) { return invoke<Record<string, any>>("dashboard", { sessionToken }); }
export function getAptitudeUsage(sessionToken: string) { return invoke<Record<string, any>>("usage_summary", { sessionToken }); }
export function getMixedTestConfig(sessionToken: string) { return invoke<MixedTestConfig>("mixed_test_config", { sessionToken }); }
export function saveMixedTestConfig(sessionToken: string, categories: Pick<MixedTestCategory, "category_id" | "question_count">[]) { return invoke<MixedTestConfig>("save_mixed_test_config", { sessionToken, categories }); }
export function createAptitudeTest(sessionToken: string, payload: Record<string, unknown>) { return invoke<{ test_id: string; status: string }>("create_test", { ...payload, sessionToken }); }
export function getAptitudeQuestion(sessionToken: string, testId: string) {
  return invoke<Record<string, any>>("question", { sessionToken, test_id: testId }).then((raw) => {
    const remainingSeconds = Number(raw.remaining_seconds ?? raw.allowed_time_seconds ?? raw.allowed_seconds ?? 0);
    return {
      ...raw,
      test_id: String(raw.test_id ?? testId),
      total_questions: Number(raw.total_questions ?? raw.total ?? 0),
      allowed_time_seconds: Number(raw.allowed_time_seconds ?? raw.allowed_seconds ?? 0),
      remaining_seconds: remainingSeconds,
      // An absolute deadline keeps the UI accurate through re-renders,
      // background-tab throttling, and locally persisted chat state.
      deadline_at_ms: Date.now() + Math.max(0, remainingSeconds) * 1000,
    } as AptitudeQuestion;
  });
}
export function submitAptitudeAnswer(sessionToken: string, testId: string, selected_answer: string, timed_out = false) { return invoke<AptitudeAnswerResult>("answer", { sessionToken, test_id: testId, selected_answer, timed_out }); }
export function requestAptitudeHint(sessionToken: string, testId: string) { return invoke<{ hint: string; hints_remaining: number }>("hint", { sessionToken, test_id: testId }); }
export function abandonAptitudeTest(sessionToken: string, testId: string) { return invoke<{ test_id: string; status: string; abandoned: boolean }>("abandon", { sessionToken, test_id: testId }); }
export function getAptitudeResults(sessionToken: string, testId: string) { return invoke<Record<string, any>>("results", { sessionToken, test_id: testId }); }
export function downloadAptitudeReport(sessionToken: string, testId: string) { return invoke<{ data: string; filename: string }>("download_report", { sessionToken, test_id: testId }); }
