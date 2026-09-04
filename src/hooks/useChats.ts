import { useCallback } from "react";
import type { Chat } from "../types";

function chatsKey(email: string) {
  return `digidara_chats_${email}`;
}

export function useChats(email: string | undefined) {
  const loadChats = useCallback((): Chat[] => {
    if (!email) return [];
    return JSON.parse(localStorage.getItem(chatsKey(email)) || "[]");
  }, [email]);

  const saveChats = useCallback(
    (chats: Chat[]) => {
      if (!email) return;
      localStorage.setItem(chatsKey(email), JSON.stringify(chats));
    },
    [email]
  );

  return { loadChats, saveChats };
}

export function nowStr() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
