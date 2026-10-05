/** Learners see points, never tokens. The server converts a balance at the
 * account's own rate (each plan sells tokens at its own tokens-per-point);
 * the helpers here only convert agent-reported token counts with that rate
 * and format the result. */

/** New accounts, and every plan, count 2,000 tokens a point (see the
 * orchestrator's FREE_TOKENS_PER_POINT). */
export const FREE_TOKENS_PER_POINT = 2000;

export function tokensToPoints(tokens: number, tokensPerPoint?: number | null): number {
  const rate = tokensPerPoint && tokensPerPoint > 0 ? tokensPerPoint : FREE_TOKENS_PER_POINT;
  return tokens / rate;
}

/** Rounded down, so a balance is never shown higher than it is: whole points
 * from 100 up, one decimal below that ("99.3"), with fixed grouping so it
 * matches the plan text the server sends whatever the browser locale. */
export function formatPoints(points: number): string {
  const value = Math.max(0, points);
  const shown = value >= 100 ? Math.floor(value) : Math.floor(value * 10) / 10;
  return shown.toLocaleString("en-US", { maximumFractionDigits: 1 });
}

/** Fired after every agent call through the gateway, so the low-points
 * prompt can re-check the balance; `outOfPoints` is set on the gateway's
 * 402 "Not enough points". The server is what actually blocks a call
 * without points -- this only decides when to show the prompt. */
export const POINTS_CHECK_EVENT = "digidara:points-check";

export function reportPointsActivity(status: number): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(POINTS_CHECK_EVENT, { detail: { outOfPoints: status === 402 } }));
}
