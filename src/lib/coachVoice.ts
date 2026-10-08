import { speakNatural, stopSpeaking } from "./voiceEngine";

/**
 * Hybrid Voice Engine: natural voice (lib/voiceEngine.ts) with browser fallback.
 *
 * Architecture:
 * playCoachSpeech goes through the orchestrator's /voice/speak (see voiceEngine.ts);
 * the browser-voice helpers below remain for callers that build utterances.
 */

const FEMALE_VOICE_PATTERNS = [
  /Jenny.*Natural/i,
  /Aria.*Natural/i,
  /Microsoft Jenny/i,
  /Microsoft Aria/i,
  /Google US English/i,
  /Google UK English Female/i,
  /Samantha/i,
  /Victoria/i,
  /Karen/i,
  /Zira/i,
  /Natural.*English/i,
  /en-US.*female/i,
];

let activeAudioElement: HTMLAudioElement | null = null;

export function selectBestCoachVoice(): SpeechSynthesisVoice | null {
  if (typeof window === "undefined" || !window.speechSynthesis) return null;
  const voices = window.speechSynthesis.getVoices() || [];
  if (!voices.length) return null;

  for (const pattern of FEMALE_VOICE_PATTERNS) {
    const match = voices.find((v) => pattern.test(v.name) && v.lang?.startsWith("en"));
    if (match) return match;
  }

  const usFemale = voices.find(
    (v) => (v.lang === "en-US" || v.lang === "en_US") && /female|woman|natural/i.test(v.name)
  );
  if (usFemale) return usFemale;

  const usVoice = voices.find((v) => v.lang === "en-US" || v.lang === "en_US");
  if (usVoice) return usVoice;

  return voices.find((v) => v.lang?.toLowerCase().startsWith("en")) || voices[0] || null;
}

export function formatCoachSpeechText(rawText: string): string {
  if (!rawText) return "";
  let text = rawText.trim();

  // Natural comma micro-pause after greeting
  text = text.replace(
    /^(Good\s+(?:morning|afternoon|evening)|Hello|Hi|Hey)\s+([A-Z][a-zA-Z]+)(?=[,\s.!?]|$)/i,
    "$1, $2."
  );

  text = text.replace(/([.!?])\s*([A-Z])/g, "$1 $2");

  if (/^(what|how|why|when|where|who|which|can|could|would|are|is|do|did|have|has)\b/i.test(text) && !/[.!?]$/.test(text)) {
    text = `${text}?`;
  } else if (!/[.!?]$/.test(text)) {
    text = `${text}.`;
  }

  text = text.replace(/\.{2,}/g, ", ");
  text = text.replace(/[—–]/g, ", ");
  return text;
}

export interface CoachSpeechOptions {
  rate?: number;
  pitch?: number;
  volume?: number;
  voiceName?: "nova" | "shimmer" | "alloy";
  authToken?: string;
  preferNeural?: boolean;
  onStart?: () => void;
  onEnd?: () => void;
  onError?: () => void;
}

/** Stop any currently playing coach audio (both neural HTML5 audio and browser speech). */
export function stopCoachAudio(): void {
  stopSpeaking();
  if (activeAudioElement) {
    try {
      activeAudioElement.pause();
      activeAudioElement.currentTime = 0;
    } catch {}
    activeAudioElement = null;
  }
  if (typeof window !== "undefined" && window.speechSynthesis) {
    try {
      window.speechSynthesis.cancel();
    } catch {}
  }
}

/** Fallback: Play through calibrated Phase 1 browser voice. */
export function playBrowserCoachSpeech(text: string, options: CoachSpeechOptions = {}): boolean {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) {
    options.onEnd?.();
    return false;
  }

  const processedText = formatCoachSpeechText(text);
  const utterance = new SpeechSynthesisUtterance(processedText);
  utterance.rate = options.rate ?? 0.90;
  utterance.pitch = options.pitch ?? 1.02;
  utterance.volume = options.volume ?? 1.0;
  utterance.lang = "en-US";

  const voice = selectBestCoachVoice();
  if (voice) {
    utterance.voice = voice;
    utterance.lang = voice.lang || "en-US";
  }

  utterance.onstart = () => options.onStart?.();
  utterance.onend = () => options.onEnd?.();
  utterance.onerror = () => options.onEnd?.();

  window.speechSynthesis.speak(utterance);
  return true;
}

/**
 * Speak as the coach, through the natural voice engine (warm persona, English
 * or Tamil, sentence-by-sentence so it starts fast), which falls back to the
 * browser voice on its own. Only onStart and onEnd fire: an error ends in
 * the fallback, so callers that resume listening from both never resume twice.
 */
export async function playCoachSpeech(text: string, options: CoachSpeechOptions = {}): Promise<void> {
  stopCoachAudio();
  await speakNatural(formatCoachSpeechText(text), { onStart: options.onStart, onEnd: options.onEnd ?? options.onError });
}

/** Compatibility helper for existing SpeechSynthesisUtterance references. */
export function createCoachUtterance(text: string, options: CoachSpeechOptions = {}): SpeechSynthesisUtterance {
  const processedText = formatCoachSpeechText(text);
  const utterance = new SpeechSynthesisUtterance(processedText);
  utterance.rate = options.rate ?? 0.90;
  utterance.pitch = options.pitch ?? 1.02;
  utterance.volume = options.volume ?? 1.0;
  utterance.lang = "en-US";

  const voice = selectBestCoachVoice();
  if (voice) {
    utterance.voice = voice;
    utterance.lang = voice.lang || "en-US";
  }

  if (options.onStart) utterance.onstart = options.onStart;
  if (options.onEnd) utterance.onend = options.onEnd;
  if (options.onError) utterance.onerror = options.onError;

  return utterance;
}
