import { gatewayInvokeUrl, invokeAgent } from "./gatewayClient";

const INVOKE_URL = gatewayInvokeUrl(
  import.meta.env.VITE_CERTIFICATE_AGENT_AGENT_NAME,
  "certificate_agent"
);

export async function checkCertificateAgentHealth(): Promise<boolean> {
  try {
    const res = await invokeAgent<{ status: string }>(INVOKE_URL, "health", {});
    return res.status === "ok";
  } catch {
    return false;
  }
}

export interface CertificateProfileResponse {
  token: string;
  sessionToken: string;
  user: {
    id: number | string;
    name: string;
    email: string;
  };
}

export async function ensureCertificateProfile(
  userId: string,
  name: string,
  email: string
): Promise<CertificateProfileResponse> {
  return invokeAgent<CertificateProfileResponse>(INVOKE_URL, "ensure_profile", {
    user_id: userId,
    name,
    email,
  });
}

export async function startCertificateExam(token: string, topic: string) {
  return invokeAgent(INVOKE_URL, "start_exam", { sessionToken: token, topic }, 1, 60_000);
}

export async function submitCertificateExam(
  token: string,
  examId: number,
  answers: Array<{ question_id: number; answer: string }>
) {
  return invokeAgent(INVOKE_URL, "submit_exam", {
    sessionToken: token,
    exam_id: examId,
    answers,
  });
}

export async function getCertificateExamHistory(token: string) {
  return invokeAgent<Array<Record<string, unknown>>>(INVOKE_URL, "get_history", {
    sessionToken: token,
  });
}

export async function getCertificateLeaderboard(topic?: string) {
  return invokeAgent<Array<Record<string, unknown>>>(INVOKE_URL, "get_leaderboard", {
    topic,
  });
}

export async function getCertificateExamDetail(token: string, examId: number) {
  return invokeAgent(INVOKE_URL, "get_exam_detail", {
    sessionToken: token,
    exam_id: examId,
  });
}

export async function getChatSessionQuestions(token: string, sessionId: string) {
  return invokeAgent(INVOKE_URL, "get_chat_session_questions", {
    sessionToken: token,
    session_id: sessionId,
  });
}

export async function getMyCertificates(token: string) {
  return invokeAgent<Array<Record<string, unknown>>>(INVOKE_URL, "get_my_certificates", {
    sessionToken: token,
  });
}

export interface CertificateRequestInterpretation {
  intent: "rename_certificate" | "email_certificate" | "download_certificate" | "list_certificates" | "confirm" | "revise" | "cancel" | "unknown";
  reply?: string;
}

export async function interpretCertificateRequest(token: string, message: string, context?: string) {
  return invokeAgent<CertificateRequestInterpretation>(INVOKE_URL, "interpret_certificate_request", {
    sessionToken: token,
    message,
    context,
  });
}

export async function updateCertificateRecipient(token: string, certId: number, recipientName: string) {
  return invokeAgent<{ certificate_id: number; certificate_number: string; recipient_name: string }>(
    INVOKE_URL,
    "update_certificate_recipient",
    { sessionToken: token, cert_id: certId, recipient_name: recipientName },
  );
}

export async function requestCertificateEmailVerification(token: string, certId: number, email: string) {
  return invokeAgent<{ certificate_id: number; email: string; expires_in_minutes: number }>(
    INVOKE_URL,
    "request_certificate_email_verification",
    {
      sessionToken: token,
      cert_id: certId,
      email,
    },
  );
}

export async function verifyCertificateEmail(token: string, certId: number, email: string, code: string) {
  return invokeAgent<{ certificate_id: number; email: string }>(INVOKE_URL, "verify_certificate_email", {
    sessionToken: token,
    cert_id: certId,
    email,
    code,
  });
}

export async function downloadCertificatePdf(token: string, certId: number) {
  // Binary downloads bypass invokeAgent's JSON parser, so carry the same
  // DigiDARA gateway authorization header explicitly. The certificate
  // service still receives its own sessionToken in the action payload.
  const platformToken = localStorage.getItem("digidara_token");
  const response = await fetch(INVOKE_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(platformToken ? { Authorization: `Bearer ${platformToken}` } : {}),
    },
    body: JSON.stringify({
      action: "download_certificate",
      payload: { sessionToken: token, cert_id: certId },
    }),
  });

  if (!response.ok) {
    let msg = "Certificate download failed";
    try {
      const err = await response.json();
      msg = err.error || err.detail || err.message || msg;
    } catch {}
    throw new Error(msg);
  }

  const disposition = response.headers.get("content-disposition");
  const filenameMatch = disposition?.match(/filename="?([^";]+)"?/);
  const filename = filenameMatch ? filenameMatch[1] : `certificate_${certId}.pdf`;

  return {
    blob: await response.blob(),
    filename,
  };
}

export async function startCertificateChat(token: string, topic?: string) {
  return invokeAgent<{ session_id: string }>(INVOKE_URL, "start_chat", {
    sessionToken: token,
    topic,
  }, 1, 60_000);
}

export async function getCertificateChatSession(token: string, sessionId: string) {
  return invokeAgent(INVOKE_URL, "get_chat_session", {
    sessionToken: token,
    session_id: sessionId,
  });
}

export async function recoverCertificateForChatSession(token: string, sessionId: string) {
  return invokeAgent<{ certificate_id: number; certificate_number?: string }>(
    INVOKE_URL,
    "recover_chat_certificate",
    { sessionToken: token, session_id: sessionId },
  );
}

export interface ChatMessageData {
  id?: number | string;
  role: string;
  content: string;
  message_type?: string;
  metadata?: Record<string, any>;
}

export interface ChatStatusData {
  session_status: string;
  current_question_index: number;
  total_questions: number;
  score_percentage?: number | null;
  passed?: boolean | null;
  is_final?: boolean;
}

export interface ChatTurnResponse {
  messages: ChatMessageData[];
  status?: ChatStatusData;
  error?: string;
}

export async function sendCertificateChatMessage(
  token: string,
  sessionId: string,
  message: string
): Promise<ChatTurnResponse> {
  const platformToken = localStorage.getItem("digidara_token");
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 60_000);

  try {
    const response = await fetch(INVOKE_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(platformToken ? { Authorization: `Bearer ${platformToken}` } : {}),
      },
      body: JSON.stringify({
        action: "send_chat_message",
        payload: {
          sessionToken: token,
          session_id: sessionId,
          message,
        },
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      let detail = response.statusText;
      try {
        const body = await response.json();
        detail = body.error ?? body.detail ?? body.message ?? detail;
      } catch {}
      throw new Error(detail);
    }

    const text = await response.text();
    const result: ChatTurnResponse = { messages: [] };

    // Fallback if backend returns direct JSON
    if (text.trim().startsWith("{")) {
      try {
        const jsonRes = JSON.parse(text);
        if (jsonRes.messages) return jsonRes;
      } catch {}
    }

    // Parse SSE format
    const lines = text.split("\n");
    let currentEvent = "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith("event:")) {
        currentEvent = trimmed.replace("event:", "").trim();
      } else if (trimmed.startsWith("data:")) {
        const dataStr = trimmed.replace("data:", "").trim();
        if (!dataStr) continue;
        try {
          const parsed = JSON.parse(dataStr);
          if (currentEvent === "message") {
            result.messages.push(parsed);
          } else if (currentEvent === "status") {
            result.status = parsed;
          } else if (currentEvent === "error") {
            result.error = parsed.error || "An error occurred";
          }
        } catch {}
      }
    }

    return result;
  } catch (error) {
    if ((error as Error).name === "AbortError") {
      throw new Error("The chat request timed out (60s). Please try again.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export async function getCertificateChatSessions(token: string) {
  return invokeAgent<Array<Record<string, unknown>>>(INVOKE_URL, "get_chat_sessions", {
    sessionToken: token,
  });
}
