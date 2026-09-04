const ORCHESTRATOR_BASE = ((import.meta.env.VITE_GATEWAY_API_URL !== undefined ? import.meta.env.VITE_GATEWAY_API_URL : "http://127.0.0.1:8100")).replace(/\/$/, "");

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
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export async function signup(name: string, email: string, mobile: string, password: string): Promise<TokenResponse> {
  const response = await postJson("/auth/signup", { name, email, mobile, password });
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

export async function googleAuth(code: string): Promise<TokenResponse> {
  const response = await postJson("/auth/google", { code, redirect_uri: googleRedirectUri() });
  return parseAuthResponse<TokenResponse>(response);
}

export async function fetchMe(token: string): Promise<AuthUser> {
  const response = await fetch(`${ORCHESTRATOR_BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return parseAuthResponse<AuthUser>(response);
}

function postJson(path: string, body: Record<string, unknown>): Promise<Response> {
  return fetch(`${ORCHESTRATOR_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
