const ORCHESTRATOR_BASE = (
  import.meta.env.VITE_GATEWAY_API_URL !== undefined
    ? import.meta.env.VITE_GATEWAY_API_URL
    : "http://127.0.0.1:8100"
).replace(/\/$/, "");

export type AgentStateId =
  | "capstone"
  | "codeforge"
  | "aptitude"
  | "communication"
  | "resume_builder"
  | "certificate"
  | "job_fetch";

export interface RemoteAgentState {
  agentId: AgentStateId;
  chatId: string;
  state: Record<string, unknown>;
  updatedAt: string;
}

async function ensureOk(response: Response): Promise<Response> {
  if (response.ok) return response;
  let detail = response.statusText;
  try {
    const body = await response.json();
    if (typeof body.detail === "string") detail = body.detail;
  } catch {
    // Keep the HTTP status text when the body is not JSON.
  }
  throw Object.assign(new Error(detail || `HTTP ${response.status}`), { status: response.status });
}

export async function fetchAgentStates(token: string): Promise<RemoteAgentState[]> {
  const response = await ensureOk(
    await fetch(`${ORCHESTRATOR_BASE}/agent-state`, { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" }),
  );
  return (await response.json()).states as RemoteAgentState[];
}

export async function saveAgentState(
  token: string,
  agentId: AgentStateId,
  chatId: string,
  state: Record<string, unknown>,
  keepalive = false,
): Promise<void> {
  await ensureOk(
    await fetch(`${ORCHESTRATOR_BASE}/agent-state/${agentId}/${encodeURIComponent(chatId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ state }),
      keepalive,
    }),
  );
}

export async function deleteAgentState(token: string, agentId: AgentStateId, chatId: string): Promise<void> {
  await ensureOk(
    await fetch(`${ORCHESTRATOR_BASE}/agent-state/${agentId}/${encodeURIComponent(chatId)}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    }),
  );
}
