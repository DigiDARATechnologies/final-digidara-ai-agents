import { useCallback, useEffect, useRef, useState } from "react";
import { deleteAgentState, fetchAgentStates, saveAgentState, type AgentStateId } from "../lib/agentStateApi";
import {
  AGENT_STATE_IDS,
  diffStates,
  mergeSecrets,
  readLegacyStates,
  readSecrets,
  removeLegacyStates,
  splitSecrets,
  writeSecrets,
  type Snapshot,
  type StateMap,
} from "../lib/agentStateStore";

export type SaveStatus = "idle" | "loading" | "saving" | "offline" | "rejected";

/* eslint-disable @typescript-eslint/no-explicit-any -- each agent has its own state type; the store only moves JSON */
export interface AgentStateBinding {
  agentId: AgentStateId;
  states: Record<string, any>;
  merge: (updater: (previous: Record<string, any>) => Record<string, any>) => void;
  /** Drop what cannot be saved (for example File objects) before the state is stored. */
  serialize?: (state: Record<string, any>) => Record<string, any>;
}
/* eslint-enable @typescript-eslint/no-explicit-any */

const TOKEN_KEY = "digidara_token";
const SAVE_DELAY_MS = 800;
const RETRY_BASE_MS = 5000;
const RETRY_MAX_MS = 30000;

const isPermanentRejection = (error: unknown) => {
  const status = (error as { status?: number })?.status;
  return typeof status === "number" && status >= 400 && status < 500 && ![401, 408, 429].includes(status);
};

/**
 * Keeps each agent's per-chat flow state on the server instead of in browser storage.
 * Reads everything once at login, saves only the chats that changed (after a short
 * pause), removes chats that were deleted, and moves any state left in the old
 * browser keys to the server exactly once, clearing the local copy only after the
 * server has confirmed the write. Agent session tokens stay in the browser.
 */
export function useAgentStatePersistence(email: string | undefined, bindings: AgentStateBinding[]) {
  const [status, setStatus] = useState<SaveStatus>("idle");
  const bindingsRef = useRef(bindings);
  bindingsRef.current = bindings;
  const emailRef = useRef(email);
  emailRef.current = email;

  const generation = useRef(0);
  const hydrated = useRef(false);
  const snapshot = useRef<Snapshot>({});
  const rejected = useRef(new Set<string>());
  const legacyAgents = useRef(new Set<AgentStateId>());
  const inFlight = useRef<Promise<void> | null>(null);
  const saveTimer = useRef<number | undefined>(undefined);
  const retryTimer = useRef<number | undefined>(undefined);
  const retryCount = useRef(0);

  const serializeFor = useCallback((agentId: AgentStateId, state: Record<string, unknown>) => {
    const binding = bindingsRef.current.find((item) => item.agentId === agentId);
    return binding?.serialize ? binding.serialize(state) : state;
  }, []);

  const currentMaps = useCallback(() => {
    const maps: Partial<Record<AgentStateId, StateMap>> = {};
    for (const binding of bindingsRef.current) maps[binding.agentId] = binding.states;
    return maps;
  }, []);

  const clearMigratedLegacy = useCallback(() => {
    const address = emailRef.current;
    if (!address) return;
    for (const agentId of [...legacyAgents.current]) {
      const legacy = readLegacyStates(agentId, address);
      // Only forget the browser copy once the server is known to hold every chat in it.
      if (Object.keys(legacy).every((chatId) => snapshot.current[agentId]?.[chatId] !== undefined)) {
        removeLegacyStates(agentId, address);
        legacyAgents.current.delete(agentId);
      }
    }
  }, []);

  const flush = useCallback(async (keepalive = false): Promise<void> => {
    const address = emailRef.current;
    const token = localStorage.getItem(TOKEN_KEY);
    if (!address || !hydrated.current || !token) return;
    if (inFlight.current) {
      await inFlight.current;
      if (emailRef.current !== address) return;
    }
    const run = async () => {
      const gen = generation.current;
      const { changes, removals, secrets } = diffStates(snapshot.current, currentMaps(), serializeFor);
      writeSecrets(address, secrets);
      const pending = changes.filter((change) => !rejected.current.has(`${change.agentId}:${change.chatId}:${change.json}`));
      if (!pending.length && !removals.length) {
        setStatus(changes.length ? "rejected" : "idle");
        clearMigratedLegacy();
        return;
      }
      setStatus("saving");
      let sawRejection = changes.length > pending.length;
      try {
        for (const change of pending) {
          try {
            await saveAgentState(token, change.agentId, change.chatId, change.state, keepalive);
          } catch (error) {
            if (!isPermanentRejection(error)) throw error;
            rejected.current.add(`${change.agentId}:${change.chatId}:${change.json}`);
            sawRejection = true;
            continue;
          }
          if (gen !== generation.current) return;
          (snapshot.current[change.agentId] ||= {})[change.chatId] = change.json;
        }
        for (const removal of removals) {
          await deleteAgentState(token, removal.agentId, removal.chatId);
          if (gen !== generation.current) return;
          delete snapshot.current[removal.agentId]?.[removal.chatId];
        }
        retryCount.current = 0;
        clearMigratedLegacy();
        setStatus(sawRejection ? "rejected" : "idle");
      } catch {
        if (gen !== generation.current) return;
        setStatus("offline");
        window.clearTimeout(retryTimer.current);
        const delay = Math.min(RETRY_MAX_MS, RETRY_BASE_MS * 2 ** retryCount.current);
        retryCount.current += 1;
        retryTimer.current = window.setTimeout(() => void flush(), delay);
      }
    };
    inFlight.current = run().finally(() => {
      inFlight.current = null;
    });
    await inFlight.current;
  }, [clearMigratedLegacy, currentMaps, serializeFor]);

  const scheduleFlush = useCallback(() => {
    window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => void flush(), SAVE_DELAY_MS);
  }, [flush]);

  // Load this learner's saved state once per login (and again after a failed attempt).
  useEffect(() => {
    generation.current += 1;
    const gen = generation.current;
    hydrated.current = false;
    snapshot.current = {};
    rejected.current = new Set();
    legacyAgents.current = new Set();
    retryCount.current = 0;
    window.clearTimeout(saveTimer.current);
    window.clearTimeout(retryTimer.current);
    // Whatever is in memory belongs to the previous account (or to no one yet).
    for (const binding of bindingsRef.current) binding.merge(() => ({}));
    if (!email) {
      setStatus("idle");
      return;
    }
    setStatus("loading");

    const hydrate = async (attempt: number): Promise<void> => {
      const token = localStorage.getItem(TOKEN_KEY);
      if (!token) {
        setStatus("idle");
        return;
      }
      try {
        const remote = await fetchAgentStates(token);
        if (gen !== generation.current) return;
        const secrets = readSecrets(email);
        const fromServer: Partial<Record<AgentStateId, StateMap>> = {};
        for (const row of remote) {
          (fromServer[row.agentId] ||= {})[row.chatId] = mergeSecrets(row.state, secrets[row.agentId]?.[row.chatId]);
        }
        for (const binding of bindingsRef.current) {
          const legacy = readLegacyStates(binding.agentId, email);
          if (Object.keys(legacy).length) legacyAgents.current.add(binding.agentId);
          const server = fromServer[binding.agentId] || {};
          const legacyOnly = Object.fromEntries(Object.entries(legacy).filter(([chatId]) => !(chatId in server)));
          const base = { ...legacyOnly, ...server };
          // What the server holds, in the same form later comparisons use.
          for (const [chatId, state] of Object.entries(server)) {
            const { clean } = splitSecrets(binding.serialize ? binding.serialize(state) : state);
            (snapshot.current[binding.agentId] ||= {})[chatId] = JSON.stringify(clean);
          }
          // Anything opened while loading wins over what was stored.
          binding.merge((previous) => ({ ...base, ...previous }));
        }
        hydrated.current = true;
        setStatus("idle");
        scheduleFlush();
      } catch {
        if (gen !== generation.current) return;
        setStatus("offline");
        retryTimer.current = window.setTimeout(() => void hydrate(attempt + 1), Math.min(RETRY_MAX_MS, RETRY_BASE_MS * 2 ** attempt));
      }
    };
    void hydrate(0);

    return () => {
      generation.current += 1;
      window.clearTimeout(saveTimer.current);
      window.clearTimeout(retryTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [email]);

  // Save whatever changed.
  const dependencies = AGENT_STATE_IDS.map((agentId) => bindings.find((binding) => binding.agentId === agentId)?.states);
  useEffect(() => {
    if (!email || !hydrated.current) return;
    scheduleFlush();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencies);

  // Do not lose the last few seconds of work when the tab is closed or hidden.
  useEffect(() => {
    const hasUnsaved = () => {
      if (!emailRef.current || !hydrated.current) return false;
      const { changes, removals } = diffStates(snapshot.current, currentMaps(), serializeFor);
      return changes.length > 0 || removals.length > 0;
    };
    const onHidden = () => {
      if (document.visibilityState === "hidden" && hasUnsaved()) void flush(true);
    };
    const onUnload = (event: BeforeUnloadEvent) => {
      if (!hasUnsaved()) return;
      void flush(true);
      event.preventDefault();
      event.returnValue = "";
    };
    document.addEventListener("visibilitychange", onHidden);
    window.addEventListener("beforeunload", onUnload);
    return () => {
      document.removeEventListener("visibilitychange", onHidden);
      window.removeEventListener("beforeunload", onUnload);
    };
  }, [currentMaps, flush, serializeFor]);

  const flushNow = useCallback(async () => {
    window.clearTimeout(saveTimer.current);
    await flush();
  }, [flush]);

  return { status, flushNow };
}
