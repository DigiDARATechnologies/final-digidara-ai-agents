/** Opening the links Boss makes (see the orchestrator's app/links): a shared
 * chat at /shared/chat/<token>, a certificate download at
 * /certificate-link/<token>. Both need the viewer to be signed in. */
import type { SharedLink } from "./linkPaths";
import { sessionToken } from "./session";

export type { SharedLink };

const ORCHESTRATOR_BASE = ((import.meta.env.VITE_GATEWAY_API_URL !== undefined ? import.meta.env.VITE_GATEWAY_API_URL : "http://127.0.0.1:8100")).replace(/\/$/, "");

export interface SharedChat {
  title: string;
  agent_id: string;
  mode: "private" | "public";
  is_owner: boolean;
  owner_name: string;
  /** The owner's own chat id (only for the owner), to open it in their chat list. */
  chat_id: string | null;
  messages: Array<{ role: string; text: string; time: string }>;
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const token = sessionToken();
  const response = await fetch(`${ORCHESTRATOR_BASE}${path}`, {
    ...init,
    headers: { ...(init.headers || {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (!response.ok) {
    let detail = "This link could not be opened.";
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // Keep the general message.
    }
    throw new Error(detail);
  }
  return response;
}

export async function openSharedChat(token: string): Promise<SharedChat> {
  return (await request(`/links/chat/${encodeURIComponent(token)}`)).json();
}

/** Whether this account can download with the certificate link (throws with the reason if not). */
export async function checkCertificateLink(token: string): Promise<void> {
  await request(`/links/certificate/${encodeURIComponent(token)}`);
}

export async function downloadCertificateLink(token: string): Promise<{ blob: Blob; filename: string }> {
  const response = await request(`/links/certificate/${encodeURIComponent(token)}/download`, { method: "POST" });
  const disposition = response.headers.get("content-disposition");
  const match = disposition?.match(/filename="?([^";]+)"?/);
  return { blob: await response.blob(), filename: match ? match[1] : "certificate.pdf" };
}
