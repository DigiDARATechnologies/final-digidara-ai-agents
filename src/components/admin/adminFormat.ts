import { AGENTS } from "../../data/agents";

const money = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });
export const formatMoney = (value: number) => money.format(value || 0);
export const formatNumber = (value: number) => new Intl.NumberFormat("en-IN").format(value || 0);

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso.endsWith("Z") || /[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);   // the server stores UTC without a marker
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString([], { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** The chat's agent id ("capstone-project") as the name students know. */
export function agentLabel(agentId: string): string {
  const agent = AGENTS.find((candidate) => candidate.id === agentId);
  return agent ? `${agent.icon} ${agent.name}` : agentId;
}

export function timeAgo(seconds: number | null): string {
  if (seconds === null) return "never";
  if (seconds < 90) return `${seconds}s ago`;
  if (seconds < 5400) return `${Math.round(seconds / 60)} min ago`;
  if (seconds < 172800) return `${Math.round(seconds / 3600)} h ago`;
  return `${Math.round(seconds / 86400)} days ago`;
}

export const PAYMENT_BADGE: Record<string, string> = { paid: "badge-active", created: "badge-pending", failed: "badge-rejected" };
