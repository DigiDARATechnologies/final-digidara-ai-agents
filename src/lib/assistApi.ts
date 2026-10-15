import { sessionToken } from "./session";

const ORCHESTRATOR_BASE = ((import.meta.env.VITE_GATEWAY_API_URL !== undefined ? import.meta.env.VITE_GATEWAY_API_URL : "http://127.0.0.1:8100")).replace(/\/$/, "");

export interface AssistRequest {
  message: string;
  history: Array<{ role: "user" | "assistant"; content: string }>;
  agentId: string;
  agentName: string;
  /** The newest lines of the chat on screen. */
  context: string;
  /** A JPEG data URL of the page (see screenCapture.ts), when the learner wants Boss to look. */
  screenshot?: string | null;
  voice?: boolean;
}

/** Boss guiding a learner on any screen (POST /chat/assist/stream): `onText`
 * gets the answer so far each time more of it arrives. Resolves with the full
 * answer. */
export async function assistStream(request: AssistRequest, onText: (text: string) => void, signal?: AbortSignal): Promise<string> {
  const token = sessionToken();
  const response = await fetch(`${ORCHESTRATOR_BASE}/chat/assist/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({
      message: request.message,
      history: request.history,
      agent_id: request.agentId,
      agent_name: request.agentName,
      context: request.context,
      screenshot: request.screenshot ?? null,
      voice: Boolean(request.voice),
    }),
    signal,
  });
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `Boss could not answer (${response.status}).`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let text = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const line = buffer.slice(0, boundary).trim();
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");
      if (!line.startsWith("data:")) continue;
      const event = JSON.parse(line.slice(5)) as { delta?: string; replace?: string; done?: boolean; reply?: string; error?: string };
      if (event.error) throw new Error(event.error);
      if (event.delta) { text += event.delta; onText(text); }
      if (event.replace !== undefined) { text = event.replace; onText(text); }
      if (event.done) return event.reply ?? text;
    }
  }
  if (!text) throw new Error("Boss could not answer just now. Please try again.");
  return text;
}
