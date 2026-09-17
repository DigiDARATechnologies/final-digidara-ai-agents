import { useCallback, useEffect, useRef } from "react";
import type { Chat } from "../types";
import { fetchChatHistory, syncChatHistory } from "../lib/chatApi";

function chatsKey(email: string) {
  return `digidara_chats_${email}`;
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
      const chats = JSON.parse(localStorage.getItem(chatsKey(email)) || "[]") as Chat[];
      knownChatIds.current = new Set(chats.map((chat) => chat.id));
      return chats;
    } catch {
      localStorage.removeItem(chatsKey(email));
      knownChatIds.current = new Set();
      return [];
    }
  }, [email]);

  const saveChats = useCallback(
    (chats: Chat[]) => {
      if (!email) return;
      const serialized = JSON.stringify(chats);
      localStorage.setItem(chatsKey(email), serialized);
      const snapshot = JSON.parse(serialized) as Chat[];
      const nextIds = new Set(snapshot.map((chat) => chat.id));
      const deletedIds = [...knownChatIds.current].filter((chatId) => !nextIds.has(chatId));
      knownChatIds.current = nextIds;
      mutationVersion.current += 1;

      const token = localStorage.getItem("digidara_token");
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
    const token = localStorage.getItem("digidara_token");
    if (!token) return null;
    const versionAtStart = mutationVersion.current;

    try {
      const remote = await fetchChatHistory(token);
      if (mutationVersion.current !== versionAtStart) return null;

      const accountChats = localChats.length || !remote.initialized
        ? (await syncChatHistory(token, localChats, [])).chats
        : remote.chats;
      if (mutationVersion.current !== versionAtStart) return null;

      localStorage.setItem(chatsKey(email), JSON.stringify(accountChats));
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
