import type { Agent } from "../types";

/** Pinned agents first (in the order they were pinned), then the rest as they were. */
export function pinnedFirst<T extends Pick<Agent, "id">>(agents: T[], pinned: string[] = []): T[] {
  if (!pinned.length) return agents;
  const rank = (agent: T) => {
    const index = pinned.indexOf(agent.id);
    return index === -1 ? pinned.length : index;
  };
  return [...agents].sort((a, b) => rank(a) - rank(b));
}
