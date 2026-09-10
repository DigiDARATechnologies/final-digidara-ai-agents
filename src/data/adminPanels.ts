/** Registry of admin panels shown in AdminShell's sidebar — one entry per
 * agent that exposes admin actions. Adding a future agent's admin panel is
 * one more entry here plus a `case` in AdminShell's render switch; no other
 * agent's files change (mirrors data/agents.ts's extensibility for the
 * student-facing chat cards). */
export interface AdminPanelMeta {
  id: string;
  label: string;
  icon: string;
  desc: string;
}

export const ADMIN_PANELS: AdminPanelMeta[] = [
  {
    id: "job-agent",
    label: "Job Fetching Agent",
    icon: "🔎",
    desc: "Job moderation queue, scraper source health, Greenhouse/Apify collection, and user plan tiers.",
  },
];

