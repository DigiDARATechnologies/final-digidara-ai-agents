import { sessionToken, setSessionToken } from "./session";

const RAW_BASE = (import.meta.env.VITE_GATEWAY_API_URL !== undefined ? import.meta.env.VITE_GATEWAY_API_URL : "http://127.0.0.1:8100");
const BASE = RAW_BASE.endsWith("/") ? RAW_BASE.slice(0, -1) : RAW_BASE;

export type DateFormat = "auto" | "dmy" | "mdy" | "ymd";

/** Settings that follow the account to every device (see the orchestrator's app/account/preferences.py). */
export interface AccountPrefs {
  notifications: { email: boolean; in_app: boolean; assessment_reminders: boolean; low_coin_warning: boolean; weekly_progress: boolean };
  general: { default_agent: string; time_zone: string; date_format: DateFormat };
  usage: { warn_percent: number };
  billing: { billing_email: string; renewal_reminder: boolean };
  pinned_agents: string[];
}

export const DEFAULT_ACCOUNT_PREFS: AccountPrefs = {
  notifications: { email: true, in_app: true, assessment_reminders: true, low_coin_warning: true, weekly_progress: false },
  general: { default_agent: "", time_zone: "", date_format: "auto" },
  usage: { warn_percent: 80 },
  billing: { billing_email: "", renewal_reminder: true },
  pinned_agents: [],
};

export type AccountPrefsPatch = { [K in keyof AccountPrefs]?: AccountPrefs[K] extends unknown[] ? AccountPrefs[K] : Partial<AccountPrefs[K]> };

export interface SignIn { id: string; method: "password" | "google" | "signup" | "two_step"; device: string; ip: string | null; created_at: string; revoked_at: string | null; active: boolean; current: boolean; }
export interface TwoStepStatus { enabled: boolean; available: boolean; password_account: boolean; email: string; }
export interface UsageRow { tokens: number; points: number; requests: number; }
export interface UsageRange {
  start: string; end: string; tokens_used: number; points_used: number; requests: number;
  agents: Array<UsageRow & { agent_name: string }>;
  days: Array<UsageRow & { day: string }>;
  events: Array<{ at: string; agent_name: string; action: string; tokens: number; points: number }>;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${sessionToken() || ""}`, ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : Array.isArray(body.detail) ? body.detail[0]?.msg : null;
    throw new Error(detail || "Something went wrong. Please try again.");
  }
  return response.json();
}

export const fetchAccountPrefs = () => request<AccountPrefs>("/account/preferences");
export const saveAccountPrefs = (patch: AccountPrefsPatch) => request<AccountPrefs>("/account/preferences", { method: "PUT", body: JSON.stringify(patch) });
export const updateProfile = (name: string, mobile: string) =>
  request<{ name: string; mobile: string | null }>("/account/profile", { method: "PUT", body: JSON.stringify({ name, mobile }) });

export const fetchSignIns = () => request<{ sign_ins: SignIn[] }>("/account/sign-ins").then((body) => body.sign_ins);
export const revokeSignIn = (id: string) => request<{ revoked: boolean }>(`/account/sign-ins/${encodeURIComponent(id)}`, { method: "DELETE" });
/** Signs out every other device; this one gets a fresh token. */
export async function signOutOtherDevices(): Promise<void> {
  const body = await request<{ access_token: string }>("/account/sign-ins/sign-out-others", { method: "POST" });
  setSessionToken(body.access_token);
}

export const fetchTwoStep = () => request<TwoStepStatus>("/account/two-step");
export const startTwoStep = (password: string) => request<{ message: string }>("/account/two-step/start", { method: "POST", body: JSON.stringify({ password }) });
export const enableTwoStep = (code: string) => request<{ enabled: boolean }>("/account/two-step/enable", { method: "POST", body: JSON.stringify({ code }) });
export const disableTwoStep = (password: string) => request<{ enabled: boolean }>("/account/two-step/disable", { method: "POST", body: JSON.stringify({ password }) });

export const fetchUsageRange = (start: string, end: string) =>
  request<UsageRange>(`/account/usage?start=${start}&end=${end}&offset_minutes=${-new Date().getTimezoneOffset()}`);

const CACHE_KEY = "digidara_account_prefs";

/** The last preferences seen on this device, so the app can use them before the server answers. */
export function cachedAccountPrefs(): AccountPrefs {
  try {
    const parsed = JSON.parse(localStorage.getItem(CACHE_KEY) || "null") as Partial<AccountPrefs> | null;
    if (!parsed || typeof parsed !== "object") return DEFAULT_ACCOUNT_PREFS;
    return {
      notifications: { ...DEFAULT_ACCOUNT_PREFS.notifications, ...parsed.notifications },
      general: { ...DEFAULT_ACCOUNT_PREFS.general, ...parsed.general },
      usage: { ...DEFAULT_ACCOUNT_PREFS.usage, ...parsed.usage },
      billing: { ...DEFAULT_ACCOUNT_PREFS.billing, ...parsed.billing },
      pinned_agents: Array.isArray(parsed.pinned_agents) ? parsed.pinned_agents.filter((id) => typeof id === "string") : [],
    };
  } catch {
    return DEFAULT_ACCOUNT_PREFS;
  }
}

export function cacheAccountPrefs(prefs: AccountPrefs | null): void {
  try {
    if (prefs) localStorage.setItem(CACHE_KEY, JSON.stringify(prefs));
    else localStorage.removeItem(CACHE_KEY);
  } catch {
    /* storage unavailable */
  }
}

/** Merge a patch locally, the same way the server does, for an instant UI. */
export function mergePrefs(prefs: AccountPrefs, patch: AccountPrefsPatch): AccountPrefs {
  const next = { ...prefs } as Record<string, unknown>;
  for (const [key, value] of Object.entries(patch)) {
    const current = (prefs as unknown as Record<string, unknown>)[key];
    next[key] = Array.isArray(value) || typeof value !== "object" || value === null ? value : { ...(current as object), ...value };
  }
  return next as unknown as AccountPrefs;
}
