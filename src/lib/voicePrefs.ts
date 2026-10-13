/** The learner's voice settings, kept on this device. */
/** One voice for the whole platform: Nila, a friendly Indian coach. */
export type VoicePersona = "nila";
export type VoiceLanguage = "auto" | "en" | "ta";

export interface VoicePrefs {
  enabled: boolean;
  /** Always "natural": every agent speaks with the one DigiDARA voice. */
  mode: "natural";
  persona: VoicePersona;
  language: VoiceLanguage;
  /** Playback speed, 0.8 to 1.3. */
  speed: number;
}

export const VOICE_PERSONAS: { id: VoicePersona; label: string; description: string }[] = [
  { id: "nila", label: "Nila", description: "Friendly Indian coach, slow and clear" },
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
    // Earlier versions let learners pick other voices or the device voice;
    // everyone now hears the same voice.
    prefs.persona = DEFAULTS.persona;
    if (!VOICE_LANGUAGES.some((l) => l.id === prefs.language)) prefs.language = DEFAULTS.language;
    prefs.mode = "natural";
    // Every agent speaks and listens in English.
    prefs.language = "en";
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

/** The speech-recognition locale: every agent listens in (Indian) English. */
export function recognitionLocale(): string {
  return "en-IN";
}
