import { useCallback, useEffect, useState } from "react";

/** Runs `load` on mount and whenever `deps` change; exposes loading/error and a manual reload. */
export function useLoad<T>(load: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    load()
      .then((result) => { if (active) setData(result); })
      .catch((caught) => { if (active) setError((caught as Error).message || "Could not load this."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const reload = useCallback(() => setTick((value) => value + 1), []);
  return { data, error, loading, reload };
}
