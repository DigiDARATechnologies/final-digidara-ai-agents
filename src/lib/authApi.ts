function getOrchestratorBase(): string {
  const globalProcess = (globalThis as unknown as { process?: { env?: Record<string, string> } }).process;
  if (globalProcess?.env?.VITE_GATEWAY_API_URL !== undefined) {
    return globalProcess.env.VITE_GATEWAY_API_URL.replace(/\/$/, "");
  }
  // `!== undefined`, not a truthy check: production intentionally builds
  // with VITE_GATEWAY_API_URL="" so the browser calls relative paths and
  // nginx reverse-proxies them to the orchestrator (see README-docker.md).
  // A truthy check would treat that deliberate empty string the same as
  // "unset" and fall through to the localhost default below, defeating the
  // relative-path setup -- gatewayClient.ts already gets this right, which
  // is why chat/agent-invoke calls work in production but this didn't.
  if (import.meta.env.VITE_GATEWAY_API_URL !== undefined) {
    return String(import.meta.env.VITE_GATEWAY_API_URL).replace(/\/$/, "");
  }
  return "http://127.0.0.1:8100";
}

const ORCHESTRATOR_BASE = getOrchestratorBase();

export function normalizeAuthError(error: unknown): string {
  if (error instanceof Error) {
    const message = error.message.trim();
    if (!message) return "Unable to reach the DigiDARA server. Please make sure the backend is running and try again.";
    if (message === "Failed to fetch" || message.toLowerCase().includes("failed to fetch") || message.toLowerCase().includes("networkerror") || message.toLowerCase().includes("load failed")) {
      return "Unable to reach the DigiDARA server. Please make sure the backend is running and try again.";
    }
    return message;
  }
  return "Unable to reach the DigiDARA server. Please make sure the backend is running and try again.";
}

async function parseAuthResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // Keep the HTTP status text when an upstream response is not JSON.
    }
    throw new Error(detail);
  }
  return response.json();
}

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  mobile: string | null;
  is_admin: boolean;
  consent_accepted_at: string | null;
  consent_policy_version: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export async function signup(name: string, email: string, mobile: string, password: string, consent: boolean): Promise<TokenResponse> {
  const response = await postJson("/auth/signup", { name, email, mobile, password, consent });
  return parseAuthResponse<TokenResponse>(response);
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const response = await postJson("/auth/login", { email, password });
  return parseAuthResponse<TokenResponse>(response);
}

/** Where Google redirects the browser back to after consent — must exactly
 * match a redirect URI registered on the Google OAuth client. */
export function googleRedirectUri(): string {
  return `${window.location.origin}/auth/google/callback`;
}

/** Builds the URL that starts Google's authorization-code flow. `state` is
 * an opaque, caller-generated value round-tripped by Google unchanged —
 * used to guard against CSRF on the callback. */
export function googleAuthUrl(state: string): string {
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: googleRedirectUri(),
    response_type: "code",
    scope: "openid email profile",
    access_type: "online",
    prompt: "select_account",
    state,
  });
  return `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
}

export async function googleAuth(code: string, consent: boolean): Promise<TokenResponse> {
  const response = await postJson("/auth/google", { code, redirect_uri: googleRedirectUri(), consent });
  return parseAuthResponse<TokenResponse>(response);
}

export async function fetchMe(token: string): Promise<AuthUser> {
  const response = await fetch(`${ORCHESTRATOR_BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return parseAuthResponse<AuthUser>(response);
}

/** DPDP Act 2023 right to access — every piece of personal data the
 * platform holds about the caller, as a JSON document. */
export async function exportMyData(token: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${ORCHESTRATOR_BASE}/auth/me/export`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return parseAuthResponse<Record<string, unknown>>(response);
}

/** DPDP Act 2023 right to erasure / consent withdrawal. `password` is
 * required to confirm deletion of a password-based account; omit it for a
 * Google-only account. */
export async function deleteMyAccount(token: string, password?: string): Promise<void> {
  const response = await fetch(`${ORCHESTRATOR_BASE}/auth/me`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ password: password ?? null }),
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // Keep the HTTP status text when an upstream response is not JSON.
    }
    throw new Error(detail);
  }
}

export async function changePassword(
  token: string,
  currentPassword: string | undefined,
  newPassword: string,
): Promise<{ message: string }> {
  const response = await fetch(`${ORCHESTRATOR_BASE}/auth/password`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  return parseAuthResponse<{ message: string }>(response);
}

function postJson(path: string, body: Record<string, unknown>): Promise<Response> {
  return fetch(`${ORCHESTRATOR_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).catch((error) => {
    throw new Error(normalizeAuthError(error));
  });
}
