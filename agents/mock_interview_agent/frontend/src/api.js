import { reportClientWarning } from "./utils/clientLogger";

const BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api"
).replace(/\/$/, "");

export function interviewReportPdfUrl(interviewId) {
  return `${BASE_URL}/interviews/${encodeURIComponent(interviewId)}/report-pdf`;
}

export function resolveApiAssetUrl(path) {
  if (!path || /^(?:https?:|blob:|data:)/i.test(path)) return path || "";
  const browserOrigin = globalThis.location?.origin || "http://localhost";
  const apiOrigin = new URL(BASE_URL, browserOrigin).origin;
  return new URL(path, apiOrigin).toString();
}

async function readJsonResponse(res, fallbackMessage) {
  let data;
  try {
    data = await res.json();
  } catch (error) {
    reportClientWarning("api_response_json_invalid", error, {
      status_code: res.status,
      request_id: res.headers.get("X-Request-ID"),
      endpoint: res.url ? res.url.split("?")[0] : null,
    });
    data = null;
  }

  if (!res.ok || (data?.error && !data?.done)) {
    const error = new Error(data?.error || fallbackMessage);
    error.requestId = res.headers.get("X-Request-ID");
    error.statusCode = res.status;
    throw error;
  }
  return data;
}

export async function startInterview(payload) {
  const res = await fetch(`${BASE_URL}/start_interview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJsonResponse(res, "Could not start the interview.");
}

export async function getDailyUsage(studentId) {
  const res = await fetch(`${BASE_URL}/daily_usage/${studentId}`);
  return readJsonResponse(res, "Unable to load today's practice quota.");
}

export async function getActiveInterview(studentId) {
  const res = await fetch(`${BASE_URL}/active_interview/${studentId}`);
  return readJsonResponse(res, "Unable to restore the active interview.");
}

export async function submitAnswer(payload, options = {}) {
  const res = await fetch(`${BASE_URL}/submit_answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: options.signal,
  });
  return readJsonResponse(res, "Could not submit your answer.");
}

export async function transcribeAudio(blob, options = {}) {
  const formData = new FormData();
  formData.append("audio", blob, "answer.webm");
  if (options.interviewId) {
    formData.append("interview_id", String(options.interviewId));
    formData.append("question_order", String(options.questionOrder));
  }

  const res = await fetch(`${BASE_URL}/transcribe`, {
    method: "POST",
    body: formData,
    signal: options.signal,
  });
  const data = await readJsonResponse(res, "Transcription request failed.");
  return data.transcript;
}

export async function endInterview(interview_id, options = {}) {
  const res = await fetch(`${BASE_URL}/end_interview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ interview_id }),
    signal: options.signal,
  });
  return readJsonResponse(res, "Could not generate your interview results.");
}

export async function exitInterview(payload, options = {}) {
  const res = await fetch(`${BASE_URL}/exit_interview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: options.signal,
  });
  return readJsonResponse(res, "Could not exit the interview.");
}

export async function recordFocusEvent(interviewId, payload, options = {}) {
  const res = await fetch(
    `${BASE_URL}/interviews/${interviewId}/focus-events`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: options.signal,
      keepalive: true,
    }
  );
  return readJsonResponse(res, "Could not record interview focus activity.");
}

export async function getDashboard(studentId) {
  const res = await fetch(`${BASE_URL}/dashboard/${studentId}`);
  return readJsonResponse(res, "Unable to load dashboard data.");
}

export async function getProfile(studentId) {
  const res = await fetch(`${BASE_URL}/profile/${studentId}`);
  return readJsonResponse(res, "Unable to load profile.");
}

export async function updateProfile(studentId, payload) {
  const res = await fetch(`${BASE_URL}/profile/${studentId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJsonResponse(res, "Unable to update profile.");
}

export async function uploadProfileAvatar(studentId, file) {
  const formData = new FormData();
  formData.append("avatar", file);

  const res = await fetch(`${BASE_URL}/profile/${studentId}/avatar`, {
    method: "POST",
    body: formData,
  });
  return readJsonResponse(res, "Unable to upload profile photo.");
}

export async function removeProfileAvatar(studentId) {
  const res = await fetch(`${BASE_URL}/profile/${studentId}/avatar`, {
    method: "DELETE",
  });
  return readJsonResponse(res, "Unable to remove profile photo.");
}

export async function getHistory(studentId, page = 1, limit = 10) {
  const params = new URLSearchParams({
    page: String(page),
    limit: String(limit),
  });
  const res = await fetch(`${BASE_URL}/history/${studentId}?${params}`);
  return readJsonResponse(res, "Unable to load interview history.");
}

export async function getHistoryDetail(interviewId) {
  const res = await fetch(`${BASE_URL}/history/detail/${interviewId}`);
  return readJsonResponse(res, "Unable to load interview details.");
}

async function getAnalytics(path, studentId, filters = {}) {
  const params = new URLSearchParams({
    student_id: String(studentId),
    ...Object.fromEntries(
      Object.entries(filters).filter(([, value]) => value !== undefined && value !== null && value !== "")
    ),
  });
  const res = await fetch(`${BASE_URL}/analytics/${path}?${params}`);
  return readJsonResponse(res, "Unable to load AI usage analytics.");
}

export const getAnalyticsSummary = (studentId, filters) => getAnalytics("summary", studentId, filters);
export const getAnalyticsDaily = (studentId, filters) => getAnalytics("daily", studentId, filters);
export const getAnalyticsMonthly = (studentId, filters) => getAnalytics("monthly", studentId, filters);
export const getAnalyticsInterviews = (studentId, filters) => getAnalytics("interviews", studentId, filters);
export const getAnalyticsQuestions = (studentId, filters) => getAnalytics("questions", studentId, filters);
export const getAnalyticsRecent = (studentId, filters) => getAnalytics("recent", studentId, filters);
export const getAnalyticsTokenBreakdown = (studentId, filters) => getAnalytics("token-breakdown", studentId, filters);
