/** The learner's voice settings, kept on this device. */
export type VoicePersona = "nila" | "arjun" | "meera" | "kavin";
export type VoiceLanguage = "auto" | "en" | "ta";

export interface VoicePrefs {
  enabled: boolean;
  /** "natural": DigiDARA's natural voice; "device": the browser's own voice only. */
  mode: "natural" | "device";
  persona: VoicePersona;
  language: VoiceLanguage;
  /** Playback speed, 0.8 to 1.3. */
  speed: number;
}

export const VOICE_PERSONAS: { id: VoicePersona; label: string; description: string }[] = [
  { id: "nila", label: "Nila", description: "Warm, cheerful coach" },
  { id: "arjun", label: "Arjun", description: "Friendly, encouraging mentor" },
  { id: "meera", label: "Meera", description: "Calm, patient guide" },
  { id: "kavin", label: "Kavin", description: "Energetic study buddy" },
];

export const VOICE_LANGUAGES: { id: VoiceLanguage; label: string }[] = [
  { id: "auto", label: "Automatic (follows the reply)" },
  { id: "en", label: "English" },
  { id: "ta", label: "தமிழ் (Tamil)" },
];

const KEY = "digidara_voice";
const DEFAULTS: VoicePrefs = { enabled: true, mode: "natural", persona: "nila", language: "auto", speed: 1 };

export function loadVoicePrefs(): VoicePrefs {
  try {
    const stored = JSON.parse(localStorage.getItem(KEY) || "{}") as Partial<VoicePrefs>;
    const prefs = { ...DEFAULTS, ...stored };
    if (!VOICE_PERSONAS.some((p) => p.id === prefs.persona)) prefs.persona = DEFAULTS.persona;
    if (!VOICE_LANGUAGES.some((l) => l.id === prefs.language)) prefs.language = DEFAULTS.language;
    if (prefs.mode !== "device") prefs.mode = "natural";
    prefs.speed = Math.min(1.3, Math.max(0.8, Number(prefs.speed) || 1));
    prefs.enabled = prefs.enabled !== false;
    return prefs;
  } catch {
    return { ...DEFAULTS };
  }
}

export function saveVoicePrefs(prefs: VoicePrefs): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    // Private mode: the settings last for this visit only.
  }
}

export function voiceLanguagePreference(): VoiceLanguage {
  return loadVoicePrefs().language;
}

/** The speech-recognition locale for voice input in the general chat. */
export function recognitionLocale(): string {
  return voiceLanguagePreference() === "ta" ? "ta-IN" : "en-IN";
}
