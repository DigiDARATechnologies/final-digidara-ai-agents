import { gatewayInvokeUrl, invokeAgent } from "./gatewayClient";

const INVOKE_URL = gatewayInvokeUrl(import.meta.env.VITE_RESUME_BUILDER_AGENT_NAME, "resume_builder_agent");
const TIMEOUT_MS = Number(import.meta.env.VITE_RESUME_BUILDER_TIMEOUT_MS || 120000);

export interface ResumeApiError extends Error { status?: number; }

async function invoke<T>(action: string, payload: Record<string, unknown>): Promise<T> {
  return invokeAgent<T>(INVOKE_URL, action, payload);
}

function unwrap<T>(result: { data?: T } | T): T { return (result as { data?: T }).data ?? result as T; }

export async function checkResumeBuilderHealth(): Promise<boolean> {
  try { return (await invoke<{ status: string }>("health", {})).status === "ok"; } catch { return false; }
}

export async function ensureResumeProfile(userId: string, name: string, email: string) {
  return unwrap<{ user_id: string }>(await invoke("ensure_profile", { user_id: userId, name, email }));
}

export interface ResumeCreateInput {
  title: string;
  target_role: string;
  experience_level: "fresher" | "experienced";
  summary: string;
  personal_info: { name: string; email: string; phone?: string; location?: string };
  skills: Array<{ skill_name: string }>;
  experience: Array<{ company: string; role: string; start_date?: string; end_date?: string; is_current?: boolean; raw_input?: string }>;
  education: Array<{ school: string; degree?: string; field?: string; start_date?: string; end_date?: string }>;
  projects: Array<{ title: string; description?: string }>;
}

export async function createResume(userId: string, input: ResumeCreateInput) {
  return unwrap<Record<string, unknown>>(await invoke("create_resume", { user_id: userId, ...input }));
}

export async function listResumes(userId: string) {
  return unwrap<Record<string, unknown>[]>(await invoke("get_resumes", { user_id: userId }));
}

export async function analyzeResumeUpload(userId: string, file: File, targetRole = "", jobDescription = "") {
  const form = new FormData();
  form.append("action", "analyze_upload");
  form.append("payload", JSON.stringify({ user_id: userId }));
  form.append("file", file);
  if (targetRole) form.append("target_role", targetRole);
  if (jobDescription) form.append("job_description", jobDescription);
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const platformToken = localStorage.getItem("digidara_token");
    const response = await fetch(INVOKE_URL, {
      method: "POST",
      headers: platformToken ? { Authorization: `Bearer ${platformToken}` } : {},
      body: form,
      signal: controller.signal,
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) { const error = new Error(body.message || response.statusText) as ResumeApiError; error.status = response.status; throw error; }
    return unwrap<Record<string, unknown>>(body);
  } finally { window.clearTimeout(timer); }
}

export async function createImportDraft(userId: string, originalFileName: string, parsedResume: unknown, atsAnalysis: unknown, targetRole: string, experienceLevel: "fresher" | "experienced") {
  return unwrap<Record<string, unknown>>(await invoke("create_import_draft", { user_id: userId, originalFileName, parsedResume, atsAnalysis, target_role: targetRole, experience_level: experienceLevel }));
}

export async function analyzeSavedResume(userId: string, resumeId: number, jobDescription = "", targetRole = "") {
  return unwrap<Record<string, unknown>>(await invoke("analyze_resume", { user_id: userId, resume_id: resumeId, job_description: jobDescription, target_role: targetRole }));
}

export async function exportResumePdf(userId: string, resumeId: number, templateChoice?: string) {
  const platformToken = localStorage.getItem("digidara_token");
  const response = await fetch(INVOKE_URL, { method: "POST", headers: { "Content-Type": "application/json", ...(platformToken ? { Authorization: `Bearer ${platformToken}` } : {}) }, body: JSON.stringify({ action: "export_pdf", payload: { user_id: userId, resume_id: resumeId, template_choice: templateChoice } }) });
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).message || "PDF export failed");
  const filename = response.headers.get("content-disposition")?.match(/filename="?([^";]+)"?/)?.[1] || `resume-${resumeId}.pdf`;
  return { blob: await response.blob(), filename };
}
