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
export async function routeMessage(message: string, history: RouteTurn[] = []): Promise<RouteResult> {
  const token = localStorage.getItem("digidara_token");
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
