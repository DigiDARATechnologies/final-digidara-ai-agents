import { gatewayInvokeUrl, invokeAgent } from "./gatewayClient";

const INVOKE_URL = gatewayInvokeUrl(import.meta.env.VITE_CAPSTONE_AGENT_NAME, "capstone_project_agent");

function invoke<T>(action: string, payload: Record<string, unknown> = {}): Promise<T> {
  return invokeAgent<T>(INVOKE_URL, action, payload);
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // Keep the HTTP status text when an upstream response is not JSON.
    }
    throw new Error(detail);
  }
  return response.json();
}

export async function checkCapstoneHealth(): Promise<boolean> {
  try {
    const result = await invoke<{ status: string }>("health");
    return result.status === "ok";
  } catch {
    return false;
  }
}

export interface TopicOption {
  id: string;
  title: string;
  summary: string;
  medium: string;
  skills_applied: string[];
}

export interface EligibilityCheckResult {
  thread_id: string;
  eligible: boolean;
  eligibility_reason: string;
  topic_options: TopicOption[] | null;
}

export type ProjectDifficulty = "easy" | "medium" | "hard";

/** No certificate/enrollment gate — course_name doubles as whatever
 * language, role, or topic the student typed. */
export function checkEligibilityFree(name: string, email: string, phone: string, topic: string, difficulty: ProjectDifficulty = "easy") {
  return invoke<EligibilityCheckResult>("check_eligibility_free", { name, email, phone, course_name: topic, difficulty });
}

export interface TopicClarifyResult {
  ready: boolean;
  clarifying_question: string | null;
}

/** Stateless pre-check run before checkEligibilityFree: does this free-text
 * request already say enough (company/role/stack) to generate two genuinely
 * targeted topics, or should the student be asked one clarifying question
 * first? See capstoneFlow.ts's awaiting_topic_request handling. */
export function clarifyTopicRequest(description: string) {
  return invoke<TopicClarifyResult>("clarify_topic_request", { description });
}

export interface TopicChooseResult {
  thread_id: string;
  chosen_topic: Record<string, unknown>;
  requirements: Record<string, any>;
}

export function chooseTopic(thread_id: string, topic_id: string) {
  return invoke<TopicChooseResult>("choose_topic", { thread_id, topic_id });
}

export interface TimerConfirmResult {
  thread_id: string;
  deadline_at: string;
  submission_guide: Record<string, any>;
}

export function confirmTimer(thread_id: string) {
  return invoke<TimerConfirmResult>("confirm_timer", { thread_id });
}

export interface CodeQualityScore {
  structure_score?: number;
  syntax_score?: number;
  maintainability_score?: number;
  completeness_score?: number;
  total_code_score?: number;
  strengths?: string[];
  weaknesses?: string[];
  specific_line_feedback?: string[];
}

export interface VivaQuestion {
  id: number;
  question: string;
}

/** One real syntax error the backend's parser found in the submitted code. */
export interface SyntaxErrorDetail {
  path: string;
  language: string;
  line?: number | null;
  column?: number | null;
  message: string;
  source_line?: string | null;
}

export interface SubmissionResult {
  thread_id: string;
  status: string;
  submission_id?: string | null;
  revision_notes?: string | null;
  syntax_errors?: SyntaxErrorDetail[] | null;
  final_score?: number | null;
  passed?: boolean | null;
  feedback?: string | null;
  score_reasoning?: string | null;
  code_quality_score?: CodeQualityScore | null;
  viva_question?: VivaQuestion | null;
  viva_progress?: string | null;
  viva_score?: number | null;
  viva_passed?: boolean | null;
}

export interface ThreadStatus {
  thread_id: string;
  status?: string | null;
  final_score?: number | null;
  passed?: boolean | null;
  feedback?: string | null;
  revision_notes?: string | null;
  score_reasoning?: string | null;
  code_quality_score?: CodeQualityScore | null;
}

export function getThreadStatus(thread_id: string) {
  return invoke<ThreadStatus>("status", { thread_id });
}

/** Downloads the final project report (PDF). The backend only issues it once BOTH the
 * code score and the viva are passed, and returns it base64-encoded through the JSON
 * gateway -- the same shape the mock-interview agent's report uses. */
export async function downloadFinalReport(submission_id: string): Promise<void> {
  const report = await invoke<{ content_type: string; filename: string; data: string }>("download_final_report", { submission_id });
  if (report.content_type !== "application/pdf" || !report.data) throw new Error("The final report is unavailable.");
  const binary = atob(report.data);
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = report.filename || "Capstone_Project_Report.pdf";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export async function uploadSubmission(thread_id: string, docxFile: File, zipFile: File) {
  const form = new FormData();
  form.append("action", "upload_submission");
  form.append("thread_id", thread_id);
  form.append("docx_file", docxFile);
  form.append("zip_file", zipFile);
  const platformToken = localStorage.getItem("digidara_token");
  const response = await fetch(INVOKE_URL, {
    method: "POST",
    headers: platformToken ? { Authorization: `Bearer ${platformToken}` } : {},
    body: form,
  });
  return parseResponse<SubmissionResult>(response);
}

export function submitVivaAnswer(submission_id: string, question_id: number, answer: string) {
  return invoke<SubmissionResult>("submit_viva_answer", { submission_id, question_id, answer });
}

export interface QAAskResult {
  answer: string;
  tools_used: string[];
}

/** Project-scoped Q&A, grounded only in this student's own topic/requirements/
 * submitted code/report/grading result (see the backend's app/agentic/qa_agent.py).
 * Used mid-viva when the student is asking something rather than answering
 * the pending question — see capstoneFlow.ts's looksLikeQuestionNotAnswer. */
export function askProjectQuestion(thread_id: string, question: string) {
  return invoke<QAAskResult>("ask_project_question", { thread_id, question });
}
