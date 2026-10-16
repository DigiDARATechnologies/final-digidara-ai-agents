/** Where Boss's links live in this site, and keeping one across sign-in
 * (no network, so it is unit-testable). */
const PENDING_KEY = "digidara.pendingLink";

export type SharedLink = { kind: "chat" | "certificate"; token: string };

const LINK_PATH = /^\/(shared\/chat|certificate-link)\/([A-Za-z0-9_.-]{10,1200})\/?$/;

/** The link in a page path, if it is one of Boss's links. */
export function linkFromPath(path: string): SharedLink | null {
  const match = LINK_PATH.exec(path);
  if (!match) return null;
  return { kind: match[1] === "shared/chat" ? "chat" : "certificate", token: match[2] };
}

/** A link opened while signed out is kept for this tab, so it opens after sign-in. */
export function rememberPendingLink(link: SharedLink): void {
  try {
    sessionStorage.setItem(PENDING_KEY, JSON.stringify(link));
  } catch {
    // Storage blocked: the link is only lost if the sign-in leaves this page.
  }
}

export function takePendingLink(): SharedLink | null {
  try {
    const saved = sessionStorage.getItem(PENDING_KEY);
    sessionStorage.removeItem(PENDING_KEY);
    const link = saved ? JSON.parse(saved) as SharedLink : null;
    return link && (link.kind === "chat" || link.kind === "certificate") && typeof link.token === "string" ? link : null;
  } catch {
    return null;
  }
}
