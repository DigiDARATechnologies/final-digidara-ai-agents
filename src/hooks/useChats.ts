import { useCallback, useEffect, useRef } from "react";
import type { Chat } from "../types";
import { fetchChatHistory, syncChatHistory } from "../lib/chatApi";
import { sessionToken } from "../lib/session";

/**
 * Remove the pre-role-based Aptitude language picker from persisted chats.
 * New Aptitude tests choose their technical context from the learner profile,
 * so replaying this historical prompt is misleading. Only the exact legacy
 * agent prompt is removed; user answers and all assessment messages remain.
 */
export function removeLegacyAptitudeLanguagePrompt(chats: Chat[]): { chats: Chat[]; changed: boolean } {
  let changed = false;
  const cleaned = chats.map((chat) => {
    if (chat.agentId !== "aptitude") return chat;
    const messages = chat.messages.filter((message) => {
      const isLegacyPrompt = message.role === "agent" && /choose the technical aptitude language\s*\(python is the default\)/i.test(message.text);
      if (isLegacyPrompt) changed = true;
      return !isLegacyPrompt;
    });
    return messages.length === chat.messages.length ? chat : { ...chat, messages, updatedAt: Date.now() };
  });
  return { chats: cleaned, changed };
}

function chatsKey(email: string) {
  return `digidara_chats_${email}`;
}

/** Set while the chats are too big for this browser's storage: then the
 * browser keeps no copy and every load comes from the server. */
function serverOnlyKey(email: string) {
  return `digidara_chats_server_only_${email}`;
}

/** The browser keeps a copy of the chats so they open instantly; the server
 * keeps the real history. A full storage quota (about 5 MB a site) used to
 * throw out of every click that changed a chat ("QuotaExceededError ...
 * exceeded the quota") and leave the agent stuck at "Connecting you now...".
 * Now a copy that does not fit is dropped instead: never a partial copy, which
 * could be uploaded over the full history. */
function writeChatsCache(email: string, serialized: string): void {
  try {
    localStorage.setItem(chatsKey(email), serialized);
    localStorage.removeItem(serverOnlyKey(email));
  } catch {
    try {
      localStorage.removeItem(chatsKey(email));
      localStorage.setItem(serverOnlyKey(email), "1");
    } catch {
      // Storage unavailable altogether: the server copy is still kept.
    }
  }
}

function serverOnly(email: string): boolean {
  try {
    return localStorage.getItem(serverOnlyKey(email)) === "1";
  } catch {
    return false;
  }
}

export function useChats(email: string | undefined) {
  const mutationVersion = useRef(0);
  const knownChatIds = useRef(new Set<string>());
  const syncQueue = useRef<Promise<unknown>>(Promise.resolve());

  useEffect(() => {
    mutationVersion.current = 0;
    knownChatIds.current = new Set();
    syncQueue.current = Promise.resolve();
  }, [email]);

  const loadChats = useCallback((): Chat[] => {
    if (!email) return [];
    try {
      const chats = serverOnly(email) ? [] : JSON.parse(localStorage.getItem(chatsKey(email)) || "[]") as Chat[];
      knownChatIds.current = new Set(chats.map((chat) => chat.id));
      return chats;
    } catch {
      try { localStorage.removeItem(chatsKey(email)); } catch { /* storage unavailable */ }
      knownChatIds.current = new Set();
      return [];
    }
  }, [email]);

  const saveChats = useCallback(
    (chats: Chat[]) => {
      if (!email) return;
      const serialized = JSON.stringify(chats);
      writeChatsCache(email, serialized);
      const snapshot = JSON.parse(serialized) as Chat[];
      const nextIds = new Set(snapshot.map((chat) => chat.id));
      const deletedIds = [...knownChatIds.current].filter((chatId) => !nextIds.has(chatId));
      knownChatIds.current = nextIds;
      mutationVersion.current += 1;

      const token = sessionToken();
      if (!token) return;
      syncQueue.current = syncQueue.current
        .catch(() => undefined)
        .then(() => syncChatHistory(token, snapshot, deletedIds))
        .catch((error) => {
          console.warn("Could not sync chat history; the local cache is retained.", error);
        });
    },
    [email]
  );

  const loadAccountChats = useCallback(async (localChats: Chat[]): Promise<Chat[] | null> => {
    if (!email) return [];
    const token = sessionToken();
    if (!token) return null;
    const versionAtStart = mutationVersion.current;

    try {
      const remote = await fetchChatHistory(token);
      if (mutationVersion.current !== versionAtStart) return null;

      const accountChats = localChats.length || !remote.initialized
        ? (await syncChatHistory(token, localChats, [])).chats
        : remote.chats;
      if (mutationVersion.current !== versionAtStart) return null;

      writeChatsCache(email, JSON.stringify(accountChats));
      knownChatIds.current = new Set(accountChats.map((chat) => chat.id));
      return accountChats;
    } catch (error) {
      console.warn("Could not load account chat history; using the local cache.", error);
      return null;
    }
  }, [email]);

  return { loadChats, loadAccountChats, saveChats };
}

export function nowStr() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function newChatId() {
  return `c_${crypto.randomUUID()}`;
}
