export type ThemePref = "system" | "dark" | "light";
export type Accent = "blue" | "gold" | "green" | "purple" | "pink" | "orange";

export interface AppearancePrefs {
  accent: Accent;
  reduceMotion: boolean;
}

export const ACCENTS: { id: Accent; label: string; color: string }[] = [
  { id: "blue", label: "Blue", color: "#2851d8" },
  { id: "gold", label: "Gold", color: "#d99a0b" },
  { id: "green", label: "Green", color: "#16a34a" },
  { id: "purple", label: "Purple", color: "#7c3aed" },
  { id: "pink", label: "Pink", color: "#db2777" },
  { id: "orange", label: "Orange", color: "#ea580c" },
];

const KEY = "digidara_appearance";
const DEFAULTS: AppearancePrefs = { accent: "blue", reduceMotion: false };

export function loadAppearance(): AppearancePrefs {
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) || "{}") as Partial<AppearancePrefs>;
    return {
      accent: ACCENTS.some((a) => a.id === parsed.accent) ? (parsed.accent as Accent) : DEFAULTS.accent,
      reduceMotion: parsed.reduceMotion === true,
    };
  } catch {
    return DEFAULTS;
  }
}

export function saveAppearance(prefs: AppearancePrefs) {
  try {
    localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    /* storage unavailable: the choice just won't persist */
  }
}

export function applyAppearance(prefs: AppearancePrefs) {
  const root = document.documentElement;
  root.dataset.accent = prefs.accent;
  root.dataset.motion = prefs.reduceMotion ? "reduced" : "full";
}
