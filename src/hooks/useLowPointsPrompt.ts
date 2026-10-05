import { useCallback, useEffect, useRef, useState } from "react";
import { fetchTokenBalance } from "../lib/billingApi";
import { POINTS_CHECK_EVENT } from "../lib/points";

/** Below this many points the learner is asked to top up (a tenth of the
 * smallest plan's 250). */
export const LOW_POINTS_THRESHOLD = 25;

/** Re-checks triggered by agent calls are spaced out by at least this long;
 * an out-of-points (402) reply or a purchase always checks at once. */
const MIN_CHECK_INTERVAL_MS = 15_000;
const POLL_INTERVAL_MS = 60_000;
const DISMISS_KEY = "digidara_low_points_dismissed";

type Level = "low" | "out";

function readDismissed(): Level | null {
  try {
    const value = sessionStorage.getItem(DISMISS_KEY);
    return value === "low" || value === "out" ? value : null;
  } catch {
    return null;
  }
}

function writeDismissed(level: Level | null) {
  try {
    if (level) sessionStorage.setItem(DISMISS_KEY, level);
    else sessionStorage.removeItem(DISMISS_KEY);
  } catch {
    // Storage blocked: the prompt may just show again, which is harmless.
  }
}

export interface LowPointsPrompt { open: boolean; points: number | null; outOfPoints: boolean; dismiss: () => void }

/** Decides when to show the "buy points" popup. Shown once per session per
 * level: dismissing it while low keeps it away until the balance runs out,
 * and running out shows it again. A purchase that lifts the balance clears
 * both. The server enforces the balance on every agent call; this is only
 * the prompt. */
export function useLowPointsPrompt(enabled: boolean): LowPointsPrompt {
  const [state, setState] = useState({ open: false, points: null as number | null, outOfPoints: false });
  const lastCheck = useRef(0);

  const check = useCallback(async (force: boolean, gatewaySaidOut = false) => {
    if (!enabled) return;
    const now = Date.now();
    if (!force && now - lastCheck.current < MIN_CHECK_INTERVAL_MS) return;
    lastCheck.current = now;
    let points: number | null = null;
    try {
      points = (await fetchTokenBalance()).points;
    } catch {
      if (!gatewaySaidOut) return;
    }
    const out = gatewaySaidOut || (points !== null && points <= 0);
    if (!out && (points === null || points >= LOW_POINTS_THRESHOLD)) {
      writeDismissed(null);
      setState((current) => ({ ...current, open: false, points }));
      return;
    }
    const dismissed = readDismissed();
    if (dismissed === "out" || (dismissed === "low" && !out)) return;
    setState({ open: true, points, outOfPoints: out });
  }, [enabled]);

  useEffect(() => {
    if (!enabled) {
      setState({ open: false, points: null, outOfPoints: false });
      return;
    }
    void check(true);
    const onActivity = (event: Event) => {
      const out = Boolean((event as CustomEvent<{ outOfPoints?: boolean }>).detail?.outOfPoints);
      void check(out, out);
    };
    const onPurchase = () => { void check(true); };
    const onFocus = () => { void check(false); };
    window.addEventListener(POINTS_CHECK_EVENT, onActivity);
    window.addEventListener("digidara:billing-updated", onPurchase);
    window.addEventListener("focus", onFocus);
    const timer = window.setInterval(() => { if (document.visibilityState === "visible") void check(false); }, POLL_INTERVAL_MS);
    return () => {
      window.removeEventListener(POINTS_CHECK_EVENT, onActivity);
      window.removeEventListener("digidara:billing-updated", onPurchase);
      window.removeEventListener("focus", onFocus);
      window.clearInterval(timer);
    };
  }, [enabled, check]);

  const dismiss = useCallback(() => {
    setState((current) => {
      writeDismissed(current.outOfPoints ? "out" : "low");
      return { ...current, open: false };
    });
  }, []);

  return { ...state, dismiss };
}
