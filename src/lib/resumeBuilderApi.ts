import { gatewayInvokeUrl, invokeAgent } from "./gatewayClient";
import { reportPointsActivity } from "./points";

const INVOKE_URL = gatewayInvokeUrl(import.meta.env.VITE_RESUME_BUILDER_AGENT_NAME, "resume_builder_agent");
const TIMEOUT_MS = Number(import.meta.env.VITE_RESUME_BUILDER_TIMEOUT_MS || 120000);

export interface ResumeApiError extends Error { status?: number; }

async function invoke<T>(action: string, payload: Record<string, unknown>, timeoutMs?: number): Promise<T> {
  return invokeAgent<T>(INVOKE_URL, action, payload, 1, timeoutMs);
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
  personal_info: { name: string; email: string; phone?: string; location?: string; links?: string[] };
  skills: Array<{ skill_name: string }>;
  experience: Array<{ company: string; role: string; start_date?: string; end_date?: string; is_current?: boolean; raw_input?: string }>;
  education: Array<{ school: string; degree?: string; level?: string; field?: string; start_date?: string; end_date?: string; cgpa?: string; percentage?: string }>;
  projects: Array<{ title: string; description?: string }>;
  certifications?: Array<{ name: string; issuer?: string; issue_date?: string; expiry_date?: string; credential_id?: string; credential_url?: string; description?: string }>;
  achievements?: Array<{ title: string; description?: string; date?: string; organization?: string }>;
  declaration?: string;
  declaration_enabled?: boolean;
}

export async function createResume(userId: string, input: ResumeCreateInput) {
  return unwrap<Record<string, unknown>>(await invoke("create_resume", { user_id: userId, ...input }));
}

export async function listResumes(userId: string) {
  return unwrap<Record<string, unknown>[]>(await invoke("get_resumes", { user_id: userId }));
}

export async function getResume(userId: string, resumeId: number) {
  return unwrap<Record<string, unknown>>(
    await invoke("get_resume", { user_id: userId, resume_id: resumeId }),
  );
}

export async function analyzeResumeUpload(userId: string, file: File, targetRole = "", jobDescription = "") {
  if (!file || file.size === 0) {
    throw new Error("The selected file is empty. Choose the original PDF, DOCX, DOC, or TXT resume file and try again.");
  }
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
    reportPointsActivity(response.status);
    if (!response.ok) { const error = new Error(body.message || response.statusText) as ResumeApiError; error.status = response.status; throw error; }
    return unwrap<Record<string, unknown>>(body);
  } finally { window.clearTimeout(timer); }
}

export async function createImportDraft(userId: string, originalFileName: string, parsedResume: unknown, atsAnalysis: unknown, targetRole: string, experienceLevel: "fresher" | "experienced") {
  return unwrap<Record<string, unknown>>(await invoke("create_import_draft", { user_id: userId, originalFileName, parsedResume, atsAnalysis, target_role: targetRole, experience_level: experienceLevel }));
}

/** Generate grounded resume wording from imported candidate content, then let
 * the caller persist the returned editable resume. The larger timeout is
 * intentional: a whole-resume response can include several work entries. */
export async function generateImportedResume(
  userId: string,
  resume: Record<string, unknown>,
  targetRole: string,
  jobDescription = "",
) {
  return unwrap<{
    resume: Record<string, unknown>;
    role_analysis?: {
      matched_skills?: string[];
      recommended_skills_to_learn?: string[];
      missing_information?: string[];
    };
  }>(
    await invoke(
      "generate_resume",
      { user_id: userId, resume, target_role: targetRole, job_description: jobDescription },
      120_000,
    ),
  );
}

export async function updateResume(userId: string, resumeId: number, resume: Record<string, unknown>) {
  return unwrap<Record<string, unknown>>(
    await invoke("update_resume", { ...resume, user_id: userId, resume_id: resumeId }),
  );
}

export interface ResumeEditProposal {
  resume: Record<string, unknown>;
  changes: string[];
  warnings: string[];
  requires_confirmation: boolean;
}

export async function suggestResumeEdit(
  userId: string,
  resume: Record<string, unknown>,
  editRequest: string,
) {
  return unwrap<ResumeEditProposal>(
    await invoke(
      "suggest_resume_edit",
      { user_id: userId, resume, edit_request: editRequest },
      120_000,
    ),
  );
}

export async function analyzeSavedResume(userId: string, resumeId: number, jobDescription = "", targetRole = "") {
  return unwrap<Record<string, unknown>>(await invoke("analyze_resume", { user_id: userId, resume_id: resumeId, job_description: jobDescription, target_role: targetRole }));
}

export interface ResumeTemplate { id: string; name: string; description?: string; }

export async function listResumeTemplates() {
  return unwrap<ResumeTemplate[]>(await invoke("list_templates", {}));
}

export async function selectResumeTemplate(userId: string, resumeId: number, templateChoice: string) {
  return unwrap<Record<string, unknown>>(
    await invoke("select_template", { user_id: userId, resume_id: resumeId, template_choice: templateChoice }),
  );
}

/** Font family / text size / line spacing applied on top of the template. */
export interface ResumeStyle {
  font_family: string;
  font_scale: number;
  line_spacing: number;
}

export interface ResumeStyleOptions {
  font_families: Array<{ id: string; label: string }>;
  font_scales: Array<{ value: number; label: string }>;
  line_spacings: Array<{ value: number; label: string }>;
  default: ResumeStyle;
}

export const DEFAULT_RESUME_STYLE: ResumeStyle = { font_family: "template", font_scale: 1, line_spacing: 1 };

export async function listResumeStyles() {
  return unwrap<ResumeStyleOptions>(await invoke("list_resume_styles", {}));
}

/** Saves the style on the resume, so the download uses it too. */
export async function saveResumeStyle(userId: string, resumeId: number, style: ResumeStyle) {
  return unwrap<Record<string, unknown>>(
    await invoke("update_resume", { user_id: userId, resume_id: resumeId, style_settings: style }),
  );
}

/** A professional style for this resume, from the offered options only. */
export async function suggestResumeStyle(userId: string, resume: Record<string, unknown>, templateChoice?: string) {
  return invoke<{ style: ResumeStyle; reason: string; source: "ai" | "rules" }>(
    "suggest_resume_style", { user_id: userId, resume, template_choice: templateChoice },
  );
}

export async function exportResumePdf(userId: string, resumeId: number, templateChoice?: string, style?: ResumeStyle) {
  const platformToken = localStorage.getItem("digidara_token");
  const response = await fetch(INVOKE_URL, { method: "POST", headers: { "Content-Type": "application/json", ...(platformToken ? { Authorization: `Bearer ${platformToken}` } : {}) }, body: JSON.stringify({ action: "export_pdf", payload: { user_id: userId, resume_id: resumeId, template_choice: templateChoice, ...(style ? { style_settings: style } : {}) } }) });
  reportPointsActivity(response.status);
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).message || "PDF export failed");
  const filename = response.headers.get("content-disposition")?.match(/filename="?([^";]+)"?/)?.[1] || `resume-${resumeId}.pdf`;
  return { blob: await response.blob(), filename };
}

/** Render the same saved, final resume object used for download as an inline PDF. */
export async function previewResumePdf(userId: string, resume: Record<string, unknown>, templateChoice?: string, style?: ResumeStyle) {
  const platformToken = localStorage.getItem("digidara_token");
  const response = await fetch(INVOKE_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(platformToken ? { Authorization: `Bearer ${platformToken}` } : {}) },
    body: JSON.stringify({ action: "preview_resume", payload: { user_id: userId, resume, template_choice: templateChoice, ...(style ? { style_settings: style } : {}) } }),
  });
  reportPointsActivity(response.status);
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).message || "Resume preview failed");
  const blob = await response.blob();
  if (!blob.size) throw new Error("The generated preview was empty. Please try again.");
  return blob;
}

export interface ResumeChatTurnInput {
  message: string;
  step: string;
  /** What the chat last asked the candidate. */
  asked?: string;
  draft: Record<string, unknown>;
  history: Array<{ role: "student" | "agent"; text: string }>;
}

export interface ResumeChatTurnResult {
  intent: "answer" | "edit" | "question" | "other";
  /** Draft fields to replace (list fields come back complete). */
  updates: Record<string, unknown>;
  reply: string;
  memories_used?: number;
}

/** One conversational turn: the agent reads the message against the draft,
 * the recent chat and the candidate's long-term memory (mem0), and returns
 * the draft fields it adds or changes. */
export async function resumeChatTurn(userId: string, input: ResumeChatTurnInput) {
  return invoke<ResumeChatTurnResult>("resume_chat_turn", { user_id: userId, ...input }, 60_000);
}

export type WordingField = "summary" | "project" | "experience";

/** A stronger wording of what the candidate just wrote, or null when their
 * text is already good (or no suggestion could be made). Never adds facts. */
export async function suggestResumeWording(userId: string, field: WordingField, text: string, targetRole?: string) {
  const result = await invoke<{ suggestion: string | null }>(
    "suggest_wording", { user_id: userId, field, text, target_role: targetRole }, 20_000,
  );
  return result.suggestion?.trim() || null;
}
