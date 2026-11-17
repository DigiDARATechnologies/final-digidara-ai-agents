import { useCallback, useEffect, useRef, useState } from "react";
import {
  cacheAccountPrefs, cachedAccountPrefs, DEFAULT_ACCOUNT_PREFS, fetchAccountPrefs, mergePrefs, saveAccountPrefs,
  type AccountPrefs, type AccountPrefsPatch,
} from "../lib/accountApi";

export interface AccountPrefsState {
  prefs: AccountPrefs;
  /** True once the server's copy has arrived (the cached one is used until then). */
  loaded: boolean;
  /** Applies at once; reverts and rejects if the server refuses. */
  update: (patch: AccountPrefsPatch) => Promise<void>;
}

/** The signed-in account's Settings choices (see lib/accountApi.ts). */
export function useAccountPrefs(userId: string | null): AccountPrefsState {
  const [prefs, setPrefs] = useState<AccountPrefs>(() => (userId ? cachedAccountPrefs() : DEFAULT_ACCOUNT_PREFS));
  const [loaded, setLoaded] = useState(false);
  const latest = useRef(prefs);
  latest.current = prefs;

  useEffect(() => {
    setLoaded(false);
    if (!userId) {
      setPrefs(DEFAULT_ACCOUNT_PREFS);
      cacheAccountPrefs(null);
      return;
    }
    let active = true;
    fetchAccountPrefs()
      .then((server) => {
        if (!active) return;
        setPrefs(server);
        cacheAccountPrefs(server);
        setLoaded(true);
      })
      .catch(() => undefined);
    return () => { active = false; };
  }, [userId]);

  const update = useCallback(async (patch: AccountPrefsPatch) => {
    const before = latest.current;
    const optimistic = mergePrefs(before, patch);
    setPrefs(optimistic);
    try {
      const saved = await saveAccountPrefs(patch);
      setPrefs(saved);
      cacheAccountPrefs(saved);
    } catch (error) {
      setPrefs(before);
      throw error;
    }
  }, []);

  return { prefs, loaded, update };
}
