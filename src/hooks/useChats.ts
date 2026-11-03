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

/** Waits before asking again for the history (ms): a restart or a slow moment
 * must not leave the learner looking at only part of it. */
const LOAD_RETRY_MS = [2_000, 5_000, 15_000];
const SAVE_RETRIES = 4;
/** The most chat data one save request carries (characters). */
const SYNC_BATCH_CHARS = 4_000_000;

/** A short fingerprint of a chat, to tell whether it changed since it was saved. */
function chatFingerprint(serialized: string): string {
  let hash = 0x811c9dc5;
  for (let index = 0; index < serialized.length; index += 1) {
    hash = Math.imul(hash ^ serialized.charCodeAt(index), 0x01000193);
  }
  return `${serialized.length}:${hash >>> 0}`;
}

/** Chats split into requests of a safe size; a chat is never split. */
export function batchChats(chats: Chat[], limit = SYNC_BATCH_CHARS): Chat[][] {
  const batches: Chat[][] = [];
  let size = 0;
  for (const chat of chats) {
    const length = JSON.stringify(chat).length;
    if (!batches.length || size + length > limit) {
      batches.push([]);
      size = 0;
    }
    batches[batches.length - 1].push(chat);
    size += length;
  }
  return batches;
}

/**
 * The account's history on screen without losing what happened while it was
 * loading. `baseline` is what the screen showed when the load began: a chat new
 * or changed since then is kept (its save is on the way), and anything else
 * follows the server, which holds every chat.
 */
export function mergeAccountChats(current: Chat[], account: Chat[], baseline: Chat[]): Chat[] {
  const before = new Map(baseline.map((chat) => [chat.id, chat.updatedAt]));
  const changed = new Map(current
    .filter((chat) => !before.has(chat.id) || chat.updatedAt > (before.get(chat.id) as number))
    .map((chat) => [chat.id, chat]));
  const merged = account.map((chat) => {
    const mine = changed.get(chat.id);
    changed.delete(chat.id);
    return mine && mine.updatedAt >= chat.updatedAt ? mine : chat;
  });
  return [...merged, ...changed.values()];
}

export function useChats(email: string | undefined) {
  const mutationVersion = useRef(0);
  const syncQueue = useRef<Promise<unknown>>(Promise.resolve());
  // Chats the learner deleted: a chat is deleted only by asking, never because
  // it is missing from a list (a list on screen can be old or partial).
  const pendingDeletes = useRef(new Set<string>());
  const deletedHere = useRef(new Set<string>());
  const clearing = useRef(false);
  const pendingRewrites = useRef(new Set<string>());
  const latest = useRef<Chat[] | null>(null);
  const saveRetries = useRef(0);
  const retryTimer = useRef<number | undefined>(undefined);
  // What the server already has, so a save sends only what changed. Sending the
  // whole history every time meant one large history refused every save, and new
  // chats were lost on reload.
  const savedFingerprints = useRef(new Map<string, string>());

  useEffect(() => {
    mutationVersion.current = 0;
    syncQueue.current = Promise.resolve();
    pendingDeletes.current = new Set();
    deletedHere.current = new Set();
    clearing.current = false;
    pendingRewrites.current = new Set();
    latest.current = null;
    saveRetries.current = 0;
    savedFingerprints.current = new Map();
    return () => window.clearTimeout(retryTimer.current);
  }, [email]);

  const loadChats = useCallback((): Chat[] => {
    if (!email) return [];
    try {
      return serverOnly(email) ? [] : JSON.parse(localStorage.getItem(chatsKey(email)) || "[]") as Chat[];
    } catch {
      try { localStorage.removeItem(chatsKey(email)); } catch { /* storage unavailable */ }
      return [];
    }
  }, [email]);

  const upload = useCallback((token: string, snapshot: Chat[]) => {
    syncQueue.current = syncQueue.current
      .catch(() => undefined)
      .then(async () => {
        const deletes = [...pendingDeletes.current];
        const clearAll = clearing.current;
        const rewrites = [...pendingRewrites.current];
        const fingerprints = new Map(snapshot.map((chat) => [chat.id, chatFingerprint(JSON.stringify(chat))]));
        const changed = snapshot.filter((chat) => savedFingerprints.current.get(chat.id) !== fingerprints.get(chat.id));
        const batches = batchChats(changed);
        if (!batches.length && (deletes.length || clearAll)) batches.push([]);
        // One request that fails does not stop the others: every chat that can
        // be saved is saved, and the failed ones go again on the retry below.
        let failure: unknown;
        for (const [index, batch] of batches.entries()) {
          try {
            await syncChatHistory(token, batch, index === 0 ? deletes : [], index === 0 && clearAll, rewrites, false);
            batch.forEach((chat) => savedFingerprints.current.set(chat.id, fingerprints.get(chat.id) as string));
            if (index === 0) {
              deletes.forEach((chatId) => pendingDeletes.current.delete(chatId));
              if (clearAll) clearing.current = false;
            }
          } catch (error) {
            failure = failure ?? error;
          }
        }
        if (failure) throw failure;
        rewrites.forEach((chatId) => pendingRewrites.current.delete(chatId));
        saveRetries.current = 0;
      })
      .catch((error) => {
        console.warn("Could not sync chat history; the local cache is retained.", error);
        // A slow moment or a restart must not lose a save: send the newest copy again.
        if (saveRetries.current >= SAVE_RETRIES) return;
        saveRetries.current += 1;
        window.clearTimeout(retryTimer.current);
        retryTimer.current = window.setTimeout(() => {
          const current = sessionToken();
          if (current && latest.current) upload(current, latest.current);
        }, 2_000 * 2 ** saveRetries.current);
      });
  }, []);

  /** `deletedIds`: the chats the learner chose to delete with this save.
   * `clearAll`: they cleared their whole history. `rewrites`: chats they edited,
   * the only ones allowed to end up shorter than the server's copy. */
  const saveChats = useCallback(
    (chats: Chat[], deletedIds: string[] = [], clearAll = false, rewrites: string[] = []) => {
      if (!email) return;
      const serialized = JSON.stringify(chats);
      writeChatsCache(email, serialized);
      const snapshot = JSON.parse(serialized) as Chat[];
      deletedIds.forEach((chatId) => {
        pendingDeletes.current.add(chatId);
        deletedHere.current.add(chatId);
      });
      if (clearAll) clearing.current = true;
      rewrites.forEach((chatId) => pendingRewrites.current.add(chatId));
      latest.current = snapshot;
      mutationVersion.current += 1;

      const token = sessionToken();
      if (!token) return;
      upload(token, snapshot);
    },
    [email, upload]
  );

  /** The account's history (sending up what this browser has), asked for again
   * if it fails; null when it still cannot be read. */
  const loadAccountChats = useCallback(async (localChats: Chat[], retries: number[] = LOAD_RETRY_MS): Promise<Chat[] | null> => {
    if (!email) return [];
    for (let attempt = 0; attempt <= retries.length; attempt += 1) {
      const token = sessionToken();
      if (!token) return null;
      const versionAtStart = mutationVersion.current;
      try {
        const remote = await fetchChatHistory(token);
        let accountChats = remote.chats;
        if (localChats.length || !remote.initialized) {
          // Each answer holds the whole history, so the last one is up to date.
          for (const batch of localChats.length ? batchChats(localChats) : [[]]) {
            accountChats = (await syncChatHistory(token, batch, [])).chats;
          }
        }
        savedFingerprints.current = new Map(accountChats.map((chat) => [chat.id, chatFingerprint(JSON.stringify(chat))]));
        // Saved something meanwhile: that newer list stays in the browser's copy.
        if (mutationVersion.current === versionAtStart) writeChatsCache(email, JSON.stringify(accountChats));
        return accountChats.filter((chat) => !deletedHere.current.has(chat.id));
      } catch (error) {
        console.warn("Could not load account chat history; using the local cache.", error);
        if (attempt < retries.length) await new Promise((resolve) => window.setTimeout(resolve, retries[attempt]));
      }
    }
    return null;
  }, [email]);

  /** The account's history as it is now, for a tab the learner came back to. */
  const refreshAccountChats = useCallback(async (): Promise<Chat[] | null> => {
    const token = sessionToken();
    if (!email || !token) return null;
    try {
      return (await fetchChatHistory(token)).chats.filter((chat) => !deletedHere.current.has(chat.id));
    } catch (error) {
      console.warn("Could not refresh account chat history.", error);
      return null;
    }
  }, [email]);

  return { loadChats, loadAccountChats, refreshAccountChats, saveChats };
}

export function nowStr() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function newChatId() {
  return `c_${crypto.randomUUID()}`;
}
