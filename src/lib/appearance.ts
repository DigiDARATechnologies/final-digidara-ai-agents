/**
 * How the app looks and behaves on this device: Settings > Appearance and
 * Settings > Accessibility. Kept in localStorage (not on the account), so a
 * phone and a laptop can differ, and applied before sign-in.
 */
export type Accent = "blue" | "gold" | "green" | "purple" | "pink" | "orange";
export type ThemeChoice = "light" | "dark" | "system";
export type TextSize = "small" | "normal" | "large" | "xlarge";
export type BubbleStyle = "rounded" | "square" | "minimal";

export interface AppearancePrefs {
  accent: Accent;
  reduceMotion: boolean;
  theme: ThemeChoice;
  textSize: TextSize;
  compact: boolean;
  bubbles: BubbleStyle;
  highContrast: boolean;
  /** Keyboard shortcuts (Ctrl+K search, Ctrl+/ list, ...). */
  shortcuts: boolean;
  /** Show on screen what Boss says and hears in a voice conversation. */
  captions: boolean;
}

export const ACCENTS: { id: Accent; label: string; color: string }[] = [
  { id: "blue", label: "Blue", color: "#2851d8" },
  { id: "gold", label: "Gold", color: "#d99a0b" },
  { id: "green", label: "Green", color: "#16a34a" },
  { id: "purple", label: "Purple", color: "#7c3aed" },
  { id: "pink", label: "Pink", color: "#db2777" },
  { id: "orange", label: "Orange", color: "#ea580c" },
];

export const THEMES: { id: ThemeChoice; label: string }[] = [
  { id: "light", label: "Light" },
  { id: "dark", label: "Dark" },
  { id: "system", label: "Match device" },
];

export const TEXT_SIZES: { id: TextSize; label: string; scale: number }[] = [
  { id: "small", label: "Small", scale: 0.92 },
  { id: "normal", label: "Normal", scale: 1 },
  { id: "large", label: "Large", scale: 1.1 },
  { id: "xlarge", label: "Extra large", scale: 1.22 },
];

export const BUBBLE_STYLES: { id: BubbleStyle; label: string; hint: string }[] = [
  { id: "rounded", label: "Rounded", hint: "Soft round bubbles" },
  { id: "square", label: "Square", hint: "Bubbles with sharp corners" },
  { id: "minimal", label: "Minimal", hint: "No bubbles, just text" },
];

const KEY = "digidara_appearance";
export const DEFAULT_APPEARANCE: AppearancePrefs = {
  accent: "blue",
  reduceMotion: false,
  theme: "light",
  textSize: "normal",
  compact: false,
  bubbles: "rounded",
  highContrast: false,
  shortcuts: true,
  captions: false,
};

function pick<T extends string>(value: unknown, allowed: readonly { id: T }[], fallback: T): T {
  return allowed.some((item) => item.id === value) ? (value as T) : fallback;
}

export function loadAppearance(): AppearancePrefs {
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) || "{}") as Partial<AppearancePrefs>;
    const flag = (value: unknown, fallback: boolean) => (typeof value === "boolean" ? value : fallback);
    return {
      accent: pick(parsed.accent, ACCENTS, DEFAULT_APPEARANCE.accent),
      reduceMotion: parsed.reduceMotion === true,
      theme: pick(parsed.theme, THEMES, DEFAULT_APPEARANCE.theme),
      textSize: pick(parsed.textSize, TEXT_SIZES, DEFAULT_APPEARANCE.textSize),
      compact: flag(parsed.compact, DEFAULT_APPEARANCE.compact),
      bubbles: pick(parsed.bubbles, BUBBLE_STYLES, DEFAULT_APPEARANCE.bubbles),
      highContrast: flag(parsed.highContrast, DEFAULT_APPEARANCE.highContrast),
      shortcuts: flag(parsed.shortcuts, DEFAULT_APPEARANCE.shortcuts),
      captions: flag(parsed.captions, DEFAULT_APPEARANCE.captions),
    };
  } catch {
    return DEFAULT_APPEARANCE;
  }
}

export function saveAppearance(prefs: AppearancePrefs) {
  try {
    localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    /* storage unavailable: the choice just won't persist */
  }
}

/** "light" or "dark": the device's own setting when the choice is "system". */
export function resolveTheme(choice: ThemeChoice): "light" | "dark" {
  if (choice !== "system") return choice;
  try {
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  } catch {
    return "light";
  }
}

export function applyAppearance(prefs: AppearancePrefs) {
  const root = document.documentElement;
  root.dataset.accent = prefs.accent;
  root.dataset.motion = prefs.reduceMotion ? "reduced" : "full";
  root.dataset.theme = resolveTheme(prefs.theme);
  root.dataset.text = prefs.textSize;
  root.dataset.density = prefs.compact ? "compact" : "comfortable";
  root.dataset.bubbles = prefs.bubbles;
  root.dataset.contrast = prefs.highContrast ? "high" : "normal";
  root.dataset.shortcuts = prefs.shortcuts ? "on" : "off";
  root.style.setProperty("--text-scale", String(TEXT_SIZES.find((size) => size.id === prefs.textSize)?.scale ?? 1));
}

/** Re-apply when the device switches between light and dark (only matters for "system"). */
export function watchSystemTheme(onChange: () => void): () => void {
  try {
    const query = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!query) return () => undefined;
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  } catch {
    return () => undefined;
  }
}
