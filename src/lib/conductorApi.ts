/** The Conductor (orchestrator POST /conductor/interpret): what the learner
 * meant when they typed at a step that offers choices. */
import type { ChatOption } from "../types";

const RAW_BASE = import.meta.env.VITE_GATEWAY_API_URL !== undefined ? import.meta.env.VITE_GATEWAY_API_URL : "http://127.0.0.1:8100";
const BASE = RAW_BASE.endsWith("/") ? RAW_BASE.slice(0, -1) : RAW_BASE;

export type ConductorDecision =
  | { intent: "continue" }
  | { intent: "select_option"; option_value: string; option_label: string }
  | { intent: "switch_agent"; agent_name: string; agent_label: string }
  | { intent: "restart" }
  | { intent: "reply"; reply: string };

export async function interpretTurn(agentName: string, step: string, options: ChatOption[], message: string): Promise<ConductorDecision> {
  const response = await fetch(`${BASE}/conductor/interpret`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("digidara_token") || ""}` },
    body: JSON.stringify({
      agent_name: agentName,
      step: step.slice(0, 60),
      options: options.slice(0, 30).map((o) => ({ value: o.value.slice(0, 200), label: (o.label || o.value).slice(0, 300) })),
      message: message.slice(0, 500),
    }),
  });
  if (!response.ok) return { intent: "continue" };
  return (await response.json()) as ConductorDecision;
}
