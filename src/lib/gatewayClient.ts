/** Shared client for calling an agent through the orchestrator gateway
 * (`POST /gateway/agents/{name}/invoke`). Every agent's `*Api.ts` file used
 * to copy-paste this exact fetch/parse logic; centralizing it here also
 * lets every agent benefit from the same one-retry resilience against a
 * brief registry gap (e.g. an agent process restarting) instead of
 * surfacing it to the user as a hard chat error. */

export function gatewayInvokeUrl(envVarValue: string | undefined, fallbackAgentName: string): string {
  const gatewayBase = ((import.meta.env.VITE_GATEWAY_API_URL !== undefined ? import.meta.env.VITE_GATEWAY_API_URL : "http://127.0.0.1:8100")).replace(/\/$/, "");
  const agentName = envVarValue || fallbackAgentName;
  return `${gatewayBase}/gateway/agents/${encodeURIComponent(agentName)}/invoke`;
}

async function extractErrorDetail(response: Response): Promise<string> {
  let detail: string = response.statusText;
  try {
    const body = await response.json();
    const raw = body.error ?? body.detail ?? body.message ?? detail;
    // Some agents nest it as {error: {message: "..."}} rather than a plain string.
    detail = typeof raw === "string" ? raw : raw?.message ?? detail;
  } catch {
    // Keep the HTTP status text when an upstream response is not JSON.
  }
  return detail;
}

// Matches the orchestrator gateway's exact 503 wording
// (`Agent {name!r} is not registered or its heartbeat is stale.`) — the
// symptom of an agent process mid-restart, not a real failure.
const TRANSIENT_AGENT_GAP = /not registered|heartbeat is stale/i;

/** POSTs `{action, payload}` to an agent's gateway URL. Retries once, after
 * a short delay, only when the failure looks like a momentary registry gap
 * — any other error (including a second consecutive gap) surfaces normally. */
export async function invokeAgent<T>(
  invokeUrl: string,
  action: string,
  payload: Record<string, unknown> = {},
  retries = 1,
  timeoutMs = 60_000,
): Promise<T> {
  for (let attempt = 0; ; attempt++) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
    let response: Response;
    try {
      const platformToken = localStorage.getItem("digidara_token");
      response = await fetch(invokeUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(platformToken ? { Authorization: `Bearer ${platformToken}` } : {}),
        },
        body: JSON.stringify({ action, payload }),
        signal: controller.signal,
      });
    } catch (error) {
      if ((error as Error).name === "AbortError") {
        throw new Error(`The ${action.replace(/_/g, " ")} request timed out. Please try again.`);
      }
      throw error;
    } finally {
      window.clearTimeout(timeoutId);
    }
    if (response.ok) return response.json();

    const detail = await extractErrorDetail(response);
    const isTransient = response.status === 503 && TRANSIENT_AGENT_GAP.test(detail);
    if (isTransient && attempt < retries) {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      continue;
    }
    throw new Error(detail);
  }
}
