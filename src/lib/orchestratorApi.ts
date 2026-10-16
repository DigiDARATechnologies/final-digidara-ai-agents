import { audioBlobToBase64, baseAudioType } from "./voiceCapture";
import { sessionToken } from "./session";
const ORCHESTRATOR_BASE = ((import.meta.env.VITE_GATEWAY_API_URL !== undefined ? import.meta.env.VITE_GATEWAY_API_URL : "http://127.0.0.1:8100")).replace(/\/$/, "");

export interface RouteResult {
  agent_name: string | null;
  reply: string | null;
}

export interface RouteTurn {
  role: "user" | "assistant";
  content: string;
}

/** Asks the orchestrator's LLM router (POST /chat/route) which registered
 * agent — if any — best matches a general-chat message. No agent gets
 * invoked here; the caller hands off to that agent's own dedicated flow
 * when `agent_name` comes back set, or shows `reply` as a plain answer
 * when it doesn't match anything specific.
 *
 * `history` (oldest first, NOT including `message`) lets the router weigh
 * the whole conversation instead of just the latest line — without it, a
 * vague opener followed by several turns of the user adding detail never
 * accumulates enough signal to route, and the router just keeps re-asking
 * the same clarifying question forever. */
/** The general chat's microphone: the recorded question, transcribed by the
 * orchestrator with OpenAI. The text is then sent like a typed message. */
export async function transcribeGeneralAudio(audio: Blob): Promise<string> {
  const token = sessionToken();
  const response = await fetch(`${ORCHESTRATOR_BASE}/chat/transcribe`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    // The learner's voice language: Tamil questions stay in Tamil script.
    body: JSON.stringify({ audio_base64: await audioBlobToBase64(audio), mime_type: baseAudioType(audio), language: "en" }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : "Voice input could not be processed. Please type your question.");
  }
  const body = await response.json();
  return String(body.transcript ?? "");
}

/** Voice conversation opened: the orchestrator does its slow first-turn work
 * (context, memory, agent list, model connection) now, while Boss greets.
 * Fire and forget: a failure only means the first turn is not pre-warmed. */
export function warmBoss(): void {
  const token = sessionToken();
  void fetch(`${ORCHESTRATOR_BASE}/chat/warm`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  }).catch(() => undefined);
}

/**
 * routeMessage, streamed: `onText` gets the reply so far each time more of it
 * arrives, so it can be shown (and spoken) while it is still being written.
 * `voice`: the learner is talking to Boss, so the answer is kept short and
 * spoken-style. Throws before any text if streaming is unavailable.
 */
export async function routeMessageStream(
  message: string,
  history: RouteTurn[],
  options: { voice?: boolean; onText: (text: string) => void },
): Promise<RouteResult> {
  const token = sessionToken();
  const response = await fetch(`${ORCHESTRATOR_BASE}/chat/route/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ message, history, voice: Boolean(options.voice) }),
  });
  if (!response.ok || !response.body) throw new Error(`route stream ${response.status}`);
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
      const event = JSON.parse(line.slice(5)) as { delta?: string; replace?: string; done?: boolean; agent_name?: string | null; reply?: string | null; error?: string };
      if (event.error) throw new Error(event.error);
      if (event.delta) { text += event.delta; options.onText(text); }
      if (event.replace !== undefined) { text = event.replace; options.onText(text); }
      if (event.done) return { agent_name: event.agent_name ?? null, reply: event.reply ?? text };
    }
  }
  if (!text) throw new Error("route stream ended early");
  return { agent_name: null, reply: text };
}

export async function routeMessage(message: string, history: RouteTurn[] = []): Promise<RouteResult> {
  const token = sessionToken();
  const response = await fetch(`${ORCHESTRATOR_BASE}/chat/route`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, history }),
  });
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
