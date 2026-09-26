import { useMemo, useSyncExternalStore } from "react";

interface Aggregate { sum: number; count: number }
type Aggregates = Record<string, Aggregate>;
type MyRatings = Record<string, number>;
interface AskedState { chats: Record<string, number>; agents: Record<string, number> }

const AGG_KEY = "digidara_agent_ratings";
const mineKey = (userId: string) => `digidara_my_ratings_${userId}`;
const askedKey = (userId: string) => `digidara_rating_asked_${userId}`;

/** The store's starting rating counts as this many votes, so one new rating nudges the
 * average instead of replacing it. */
const SEED_WEIGHT = 5;
const DAY_MS = 24 * 60 * 60 * 1000;

function read<T>(key: string, fallback: T): T {
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || "null");
    return parsed && typeof parsed === "object" ? (parsed as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable: the rating just won't persist */
  }
}

let version = 0;
const listeners = new Set<() => void>();
function emit() {
  version += 1;
  listeners.forEach((l) => l());
}
function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export interface DisplayRating { value: number; count: number }

export function getDisplayRating(agentId: string, base = 4.5): DisplayRating {
  const agg = read<Aggregates>(AGG_KEY, {})[agentId];
  const count = agg?.count ?? 0;
  const value = (base * SEED_WEIGHT + (agg?.sum ?? 0)) / (SEED_WEIGHT + count);
  return { value, count };
}

/** Live rating for an agent; re-renders when anyone on this device submits a new rating. */
export function useAgentRating(agentId: string, base?: number): DisplayRating {
  const v = useSyncExternalStore(subscribe, () => version);
  return useMemo(() => getDisplayRating(agentId, base), [agentId, base, v]);
}

export function getMyRating(userId: string, agentId: string): number | undefined {
  return read<MyRatings>(mineKey(userId), {})[agentId];
}

/** Saves a 1-5 star rating. Rating the same agent again replaces the earlier vote. */
export function submitRating(userId: string, agentId: string, stars: number): void {
  const value = Math.min(5, Math.max(1, Math.round(stars)));
  const all = read<Aggregates>(AGG_KEY, {});
  const mine = read<MyRatings>(mineKey(userId), {});
  const agg = all[agentId] ?? { sum: 0, count: 0 };
  const previous = mine[agentId];
  all[agentId] = previous ? { sum: agg.sum - previous + value, count: agg.count } : { sum: agg.sum + value, count: agg.count + 1 };
  mine[agentId] = value;
  write(AGG_KEY, all);
  write(mineKey(userId), mine);
  emit();
}

/** A prompt is due at most once per chat, and at most once a day per agent. */
export function shouldAskForRating(userId: string, agentId: string, chatId: string): boolean {
  const asked = read<AskedState>(askedKey(userId), { chats: {}, agents: {} });
  if (asked.chats[chatId]) return false;
  const last = asked.agents[agentId];
  return !last || Date.now() - last > DAY_MS;
}

export function markAsked(userId: string, agentId: string, chatId: string): void {
  const asked = read<AskedState>(askedKey(userId), { chats: {}, agents: {} });
  const now = Date.now();
  asked.chats[chatId] = now;
  asked.agents[agentId] = now;
  write(askedKey(userId), asked);
}
