import type { Chat } from "../types";

const ORCHESTRATOR_BASE = (
  import.meta.env.VITE_GATEWAY_API_URL !== undefined
    ? import.meta.env.VITE_GATEWAY_API_URL
    : "http://127.0.0.1:8100"
).replace(/\/$/, "");

export interface RemoteChatHistory {
  chats: Chat[];
  initialized: boolean;
}

async function parseResponse(response: Response): Promise<RemoteChatHistory> {
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // Preserve the HTTP status text when the response is not JSON.
    }
    throw new Error(detail);
  }
  return response.json();
}

export async function fetchChatHistory(token: string): Promise<RemoteChatHistory> {
  const response = await fetch(`${ORCHESTRATOR_BASE}/chats`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  return parseResponse(response);
}

export async function syncChatHistory(
  token: string,
  chats: Chat[],
  deletedIds: string[],
): Promise<RemoteChatHistory> {
  const response = await fetch(`${ORCHESTRATOR_BASE}/chats/sync`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ chats, deleted_ids: deletedIds }),
  });
  return parseResponse(response);
}
