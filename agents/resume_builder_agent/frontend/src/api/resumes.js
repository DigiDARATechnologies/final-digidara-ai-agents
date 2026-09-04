const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");
const REQUEST_TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS || 15000);

export const CURRENT_USER_ID = import.meta.env.VITE_DEV_USER_ID ?? "";
let secureSessionPromise = null;

function buildApiError(message, status = 0, type) {
  const apiError = new Error(message);
  apiError.status = status;
  apiError.type = type || errorType(status);
  return apiError;
}

function errorType(status) {
  if (status === 0) return "unavailable";
  if (status === 401 || status === 403) return "auth";
  if (status === 400 || status === 422) return "validation";
  if (status === 404) return "not_found";
  if (status === 429) return "rate_limit";
  if (status === 503) return "database";
  if (status >= 500) return "server";
  return "request";
}

function statusMessage(status) {
  if (status === 401 || status === 403) return "Your secure session expired. Refresh and retry.";
  if (status === 400 || status === 422) return "Please check the resume details and retry.";
  if (status === 404) return "Resume not found.";
  if (status === 429) return "Too many requests. Please wait briefly and retry.";
  if (status === 503) return "Database is unavailable. Please retry.";
  if (status >= 500) return "Server error. Please retry.";
  return "API request failed.";
}

async function ensureSecureSession() {
  if (CURRENT_USER_ID) {
    return { csrfToken: "", userId: CURRENT_USER_ID };
  }
  if (!secureSessionPromise) {
    secureSessionPromise = fetch(`${API_BASE_URL}/session`, {
      credentials: "include",
      headers: { Accept: "application/json" },
    })
      .then(async (response) => {
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || !payload.data?.csrfToken) {
          throw buildApiError("Could not establish a secure browser session.", response.status, "auth");
        }
        return payload.data;
      })
      .catch((error) => {
        secureSessionPromise = null;
        throw error;
      });
  }
  return secureSessionPromise;
}

async function securityHeaders(method = "GET") {
  const context = await ensureSecureSession();
  if (CURRENT_USER_ID) {
    return { "X-User-Id": CURRENT_USER_ID };
  }
  return ["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase())
    ? {}
    : { "X-CSRF-Token": context.csrfToken };
}

async function request(path, options = {}) {
  const controller = new AbortController();
  // Resume optimization can require several AI calls (summary plus each
  // experience/project entry), so callers may opt into a longer timeout.
  const timeoutMs = Number(options.timeoutMs) || REQUEST_TIMEOUT_MS;
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  const method = (options.method || "GET").toUpperCase();
  const { timeoutMs: _timeoutMs, ...fetchOptions } = options;
  const headers = {
    "Content-Type": "application/json",
    ...(await securityHeaders(method)),
    ...(options.headers ?? {}),
  };
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...fetchOptions,
      credentials: "include",
      headers,
      signal: controller.signal,
    });
  } catch (error) {
    if (error.name === "AbortError") {
      throw buildApiError("Backend request timed out. Please retry.", 0, "timeout");
    }
    const displayUrl = API_BASE_URL.startsWith("http")
      ? API_BASE_URL
      : `${window.location.origin}${API_BASE_URL}`;
    throw buildApiError(`Cannot reach backend at ${displayUrl}`, 0, "unavailable");
  } finally {
    window.clearTimeout(timeoutId);
  }

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = [payload.error, payload.message, payload.detail].filter(Boolean).join(": ");
    throw buildApiError(message || statusMessage(response.status), response.status);
  }
  return payload.data ?? payload;
}

export function listResumes(filters = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value && value !== "all") params.set(key, value);
  }
  const query = params.toString();
  return request(`/resumes${query ? `?${query}` : ""}`);
}

export function listTemplates() {
  return request("/templates");
}

export function fetchTemplate(templateId) {
  return request(`/templates/${templateId}`);
}

export function createResume(title = "Untitled Resume", templateChoice = "steady-form", experienceLevel = null) {
  return request("/resume", {
    method: "POST",
    body: JSON.stringify({ title, template_choice: templateChoice, experience_level: experienceLevel }),
  });
}

export async function analyzeResumeImport({ file, jobDescription = "", targetRole = "" }) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS * 2);
  const formData = new FormData();
  formData.append("file", file);
  if (jobDescription.trim()) formData.append("job_description", jobDescription.trim());
  if (targetRole.trim()) formData.append("target_role", targetRole.trim());

  let response;
  try {
    response = await fetch(`${API_BASE_URL}/resumes/import/analyze`, {
      method: "POST",
      body: formData,
      credentials: "include",
      headers: await securityHeaders("POST"),
      signal: controller.signal,
    });
  } catch (error) {
    if (error.name === "AbortError") {
      throw buildApiError("Resume analysis timed out. Please retry.", 0, "timeout");
    }
    throw buildApiError("Cannot reach the resume analysis service.", 0, "unavailable");
  } finally {
    window.clearTimeout(timeoutId);
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw buildApiError(payload.message || statusMessage(response.status), response.status);
  }
  return payload.data ?? payload;
}

export function createImportedResumeDraft({ originalFileName, parsedResume, atsAnalysis }) {
  return request("/resumes/import/draft", {
    method: "POST",
    body: JSON.stringify({ originalFileName, parsedResume, atsAnalysis }),
  });
}

export function fetchResume(resumeId) {
  return request(`/resume/${resumeId}`);
}

export function saveResume(resumeId, resume) {
  return request(`/resume/${resumeId}`, { method: "PUT", body: JSON.stringify(resume) });
}

export async function uploadResumePhoto(resumeId, file) {
  const formData = new FormData();
  formData.append("photo", file);
  const response = await fetch(`${API_BASE_URL}/resume/${resumeId}/photo`, {
    method: "POST", body: formData, credentials: "include", headers: await securityHeaders("POST"),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw buildApiError(payload.error || payload.message || "Photo upload failed", response.status);
  return payload.data ?? payload;
}

export function duplicateResume(resumeId, title) {
  return request(`/resumes/${resumeId}/duplicate`, {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export function renameResume(resumeId, title) {
  return request(`/resumes/${resumeId}`, { method: "PATCH", body: JSON.stringify({ title }) });
}

export function archiveResume(resumeId) {
  return request(`/resumes/${resumeId}/archive`, { method: "POST", body: "{}" });
}

export function restoreResume(resumeId) {
  return request(`/resumes/${resumeId}/restore`, { method: "POST", body: "{}" });
}

export function deleteResume(resumeId) {
  return request(`/resume/${resumeId}`, { method: "DELETE" });
}

async function pdfRequest(path, body, timeoutMessage) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS * 2);
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      body: JSON.stringify(body),
      credentials: "include",
      headers: { "Content-Type": "application/json", ...(await securityHeaders("POST")) },
      signal: controller.signal,
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw buildApiError(payload.message || "PDF request failed", response.status, "pdf");
    }
    if (!(response.headers.get("Content-Type") ?? "").includes("application/pdf")) {
      throw buildApiError("The server did not return a valid PDF.", response.status, "pdf");
    }
    return response;
  } catch (error) {
    if (error.name === "AbortError") throw buildApiError(timeoutMessage, 0, "timeout");
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export async function exportResumePdf(resumeId, templateChoice) {
  const response = await pdfRequest(
    `/resumes/${resumeId}/download`,
    { templateId: templateChoice, template_choice: templateChoice },
    "PDF generation timed out. Please retry.",
  );
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = disposition.match(/filename="?([^"]+)"?/)?.[1]
    ?? `resume-${resumeId}-${templateChoice}.pdf`;
  return { blob, filename };
}

export async function previewResumePdf(resume) {
  const response = await pdfRequest(
    "/resumes/preview",
    { resume, template_choice: resume.template_choice },
    "Preview generation timed out.",
  );
  return response.blob();
}

export function generateExperienceBullets({ industry, rawInput, role, experienceLevel = null }) {
  return request("/ai/generate-bullets", {
    method: "POST",
    body: JSON.stringify({ raw_input: rawInput, role, industry, experience_level: experienceLevel }),
  });
}

export function generateProjectBullets({ rawInput, title = "", technologies = "" }) {
  return request("/ai/generate-project-bullets", {
    method: "POST",
    body: JSON.stringify({ raw_input: rawInput, title, technologies }),
  });
}

export function improveBullet({ bullet, context = {}, mode = "improve" }) {
  return request("/ai/improve-bullet", {
    method: "POST",
    body: JSON.stringify({ bullet, context, mode }),
  });
}

export function suggestSkills({ jobDescription = "", resume = {} }) {
  return request("/ai/suggest-skills", {
    method: "POST",
    body: JSON.stringify({ job_description: jobDescription, resume_json: resume }),
  });
}

export function analyzeJobDescription({ jobDescription }) {
  return request("/ai/analyze-job-description", {
    method: "POST",
    body: JSON.stringify({ job_description: jobDescription }),
  });
}

export function generateDeclaration({ location = "", name = "" } = {}) {
  return request("/ai/generate-declaration", {
    method: "POST",
    body: JSON.stringify({ location, name }),
  });
}

export function generateResumeSummary({ jobDescription = "", resume, targetRole }) {
  return request("/ai/generate-summary", {
    method: "POST",
    body: JSON.stringify({ job_description: jobDescription, resume, target_role: targetRole }),
  });
}

export function tailorResumeToJobDescription({ jobDescription, resume }) {
  return request("/ai/tailor-to-jd", {
    method: "POST",
    body: JSON.stringify({ resume_json: resume, job_description: jobDescription }),
  });
}

export function optimizeResumeWithAi({ resume, targetRole, jobDescription = "" }) {
  return request("/ai/optimize-resume", {
    method: "POST",
    body: JSON.stringify({ resume, target_role: targetRole, job_description: jobDescription }),
    // This endpoint makes one model call for the summary and additional calls
    // for every eligible experience or project. The normal 15-second API
    // timeout aborts valid requests before the generated resume can return.
    timeoutMs: Math.max(REQUEST_TIMEOUT_MS, 120000),
  });
}

export function analyzeSavedResume(resumeId, jobDescription = "", targetRole = "") {
  return request(`/resumes/${resumeId}/ats`, {
    method: "POST",
    body: JSON.stringify({ job_description: jobDescription.trim(), target_role: targetRole.trim() }),
  });
}
