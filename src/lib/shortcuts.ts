/**
 * Keyboard shortcuts (Settings > Accessibility). They can be switched off;
 * applyAppearance writes the choice to <html data-shortcuts>, so any
 * component's own shortcut (the sidebar's Ctrl+K) can check it too.
 */
export interface Shortcut { keys: string; label: string }

const mod = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent) ? "⌘" : "Ctrl";

export const SHORTCUTS: Shortcut[] = [
  { keys: `${mod} + K`, label: "Search chats" },
  { keys: `${mod} + Shift + O`, label: "Start a new chat" },
  { keys: `${mod} + ,`, label: "Open Settings" },
  { keys: `${mod} + B`, label: "Show or hide the sidebar" },
  { keys: "/", label: "Jump to the message box" },
  { keys: `${mod} + /`, label: "Show this list of shortcuts" },
  { keys: "Esc", label: "Close a window or menu" },
];

export function shortcutsEnabled(): boolean {
  return typeof document === "undefined" || document.documentElement.dataset.shortcuts !== "off";
}

export interface ShortcutActions {
  newChat: () => void;
  openSettings: () => void;
  toggleSidebar: () => void;
  showShortcuts: () => void;
}

function typingIn(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  if (!element) return false;
  const tag = element.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || element.isContentEditable;
}

/** The app-wide shortcuts. Returns true when the key was one of them. */
export function handleShortcut(event: KeyboardEvent, actions: ShortcutActions): boolean {
  if (!shortcutsEnabled() || event.altKey) return false;
  const withMod = event.ctrlKey || event.metaKey;
  const key = event.key.toLowerCase();
  if (withMod && event.shiftKey && key === "o") { actions.newChat(); return true; }
  if (withMod && !event.shiftKey && key === ",") { actions.openSettings(); return true; }
  if (withMod && !event.shiftKey && key === "b") { actions.toggleSidebar(); return true; }
  if (withMod && key === "/") { actions.showShortcuts(); return true; }
  if (!withMod && !event.shiftKey && key === "/" && !typingIn(event.target)) {
    const box = document.querySelector<HTMLTextAreaElement>("form.composer textarea, form.home-composer textarea, form.paste-composer textarea");
    if (box) { box.focus(); return true; }
  }
  return false;
}
