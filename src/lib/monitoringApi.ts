/** Boss's briefing for the monitoring accounts. The server decides who gets one;
 * everyone else is told `allowed: false`. */
import { sessionToken } from "./session";

const RAW_BASE = (import.meta.env.VITE_GATEWAY_API_URL !== undefined ? import.meta.env.VITE_GATEWAY_API_URL : "http://127.0.0.1:8100");
const BASE = RAW_BASE.endsWith("/") ? RAW_BASE.slice(0, -1) : RAW_BASE;

export interface MonitoringBriefing { allowed: boolean; issues: unknown[]; text: string; as_of?: string }

export async function fetchBriefing(recent = false): Promise<MonitoringBriefing> {
  const response = await fetch(`${BASE}/platform-admin/monitoring/briefing${recent ? "?recent=true" : ""}`, {
    headers: { Authorization: `Bearer ${sessionToken()}` }, cache: "no-store",
  });
  if (!response.ok) throw new Error(response.statusText);
  return response.json();
}

export async function markBriefingSeen(asOf: string): Promise<void> {
  await fetch(`${BASE}/platform-admin/monitoring/seen`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${sessionToken()}` },
    body: JSON.stringify({ as_of: asOf }),
  });
}
