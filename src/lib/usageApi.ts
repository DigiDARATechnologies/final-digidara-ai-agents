import { gatewayInvokeUrl, invokeAgent } from "./gatewayClient";

function aptitudeSessionToken(): string {
  try {
    const user = JSON.parse(localStorage.getItem("digidara_user") || "null") as { email?: string } | null;
    return user?.email ? localStorage.getItem(`digidara_aptitude_token_${user.email.toLowerCase()}`) || "" : "";
  } catch { return ""; }
}

export interface UsageSummary {
  agent_name: string;
  total_requests: number;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  by_request_type: Record<string, number>;
}

export interface AgentUsageResult {
  id: string;
  label: string;
  icon: string;
  color: string;
  online: boolean;
  usage: UsageSummary | null;
}

interface AgentUsageTarget {
  id: string;
  label: string;
  icon: string;
  color: string;
  invokeUrl: string;
  payload?: Record<string, unknown>;
}

// Every platform agent with an LLM behind it exposes the same "usage_summary"
// action (see each backend's routes/invoke.py) — this just fans out to both
// in parallel. Icons/colors mirror src/data/agents.ts's cards.
const TARGETS: AgentUsageTarget[] = [
  {
    id: "capstone_project_agent",
    label: "Capstone Project Agent",
    icon: "🎓",
    color: "#16a34a",
    invokeUrl: gatewayInvokeUrl(import.meta.env.VITE_CAPSTONE_AGENT_NAME, "capstone_project_agent"),
  },
  {
    id: "codeforge_agent",
    label: "LeetCode / DSA Agent",
    icon: "⌨️",
    color: "#eab308",
    invokeUrl: gatewayInvokeUrl(import.meta.env.VITE_CODEFORGE_AGENT_NAME, "codeforge_agent"),
  },
  {
    id: "aptitude_agent",
    label: "Aptitude Trainer Agent",
    icon: "🧮",
    color: "#f97316",
    invokeUrl: gatewayInvokeUrl(import.meta.env.VITE_APTITUDE_AGENT_NAME, "aptitude_agent"),
    payload: { sessionToken: aptitudeSessionToken() },
  },
  {
    id: "communication_agent",
    label: "Communication Coach Agent",
    icon: "🗣️",
    color: "#f43f5e",
    invokeUrl: gatewayInvokeUrl(import.meta.env.VITE_COMMUNICATION_AGENT_NAME, "communication_agent"),
  },
];

export async function fetchAllUsageSummaries(): Promise<AgentUsageResult[]> {
  return Promise.all(
    TARGETS.map(async (target): Promise<AgentUsageResult> => {
      try {
        const usage = await invokeAgent<UsageSummary>(target.invokeUrl, "usage_summary", target.payload);
        return { id: target.id, label: target.label, icon: target.icon, color: target.color, online: true, usage };
      } catch {
        return { id: target.id, label: target.label, icon: target.icon, color: target.color, online: false, usage: null };
      }
    }),
  );
}
