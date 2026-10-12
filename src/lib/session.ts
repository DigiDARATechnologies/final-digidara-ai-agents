/**
 * One account per browser.
 *
 * The login token lives in localStorage, which every tab shares. A tab
 * remembers the token it signed in with; when another tab signs in to a
 * different account (or signs out), sessionToken() stops returning it at
 * once -- so this tab's pending saves (chat history, agent progress) can
 * never be written into the other account -- and onSessionSwitched() lets
 * the app reload into the latest account.
 */
const TOKEN_KEY = "digidara_token";

function stored(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

let tabToken: string | null = stored();

/** This tab's login token, or null once another tab has switched the account. */
export function sessionToken(): string | null {
  const current = stored();
  return current && current === tabToken ? current : null;
}

/** Signs this tab (and so the browser) in, or out with null. */
export function setSessionToken(token: string | null): void {
  tabToken = token;
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Storage blocked (private mode): this tab still works for this session.
  }
}

/** True when another tab signed in to another account or signed out. */
export function sessionSwitched(): boolean {
  return stored() !== tabToken;
}

/** Calls `onSwitch` when another tab changes the signed-in account. */
export function onSessionSwitched(onSwitch: (signedOut: boolean) => void): () => void {
  function handle(event: StorageEvent) {
    if (event.key !== TOKEN_KEY && event.key !== null) return;
    if (!sessionSwitched()) return;
    onSwitch(!stored());
  }
  window.addEventListener("storage", handle);
  return () => window.removeEventListener("storage", handle);
}
