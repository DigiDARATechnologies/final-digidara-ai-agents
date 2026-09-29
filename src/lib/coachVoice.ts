/**
 * Hybrid Voice Engine: Neural TTS (Phase 2) with Seamless Browser Fallback (Phase 1).
 *
 * Architecture:
 * 1. Checks backend `/api/speaking/synthesize` for studio-quality Neural Audio (OpenAI tts-1 'nova').
 * 2. If backend Neural TTS is unavailable, rate-limited, or offline, immediately falls back
 *    to the calibrated local browser voice (Microsoft Jenny / Aria / Google US English).
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
 * Play speech using Phase 2 Neural Backend TTS, seamlessly falling back to Phase 1 browser voice.
 */
export async function playCoachSpeech(text: string, options: CoachSpeechOptions = {}): Promise<void> {
  stopCoachAudio();

  const preferNeural = options.preferNeural ?? true;
  const processedText = formatCoachSpeechText(text);

  if (!preferNeural || !options.authToken) {
    playBrowserCoachSpeech(processedText, options);
    return;
  }

  try {
    const response = await fetch("/api/speaking/synthesize", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${options.authToken}`,
      },
      body: JSON.stringify({
        text: processedText,
        voice: options.voiceName || "nova",
        speed: options.rate ?? 0.92,
      }),
    });

    if (!response.ok) {
      throw new Error(`Neural TTS returned ${response.status}`);
    }

    const blob = await response.blob();
    const audioUrl = URL.createObjectURL(blob);
    const audio = new Audio(audioUrl);
    activeAudioElement = audio;

    audio.onplay = () => options.onStart?.();
    audio.onended = () => {
      URL.revokeObjectURL(audioUrl);
      activeAudioElement = null;
      options.onEnd?.();
    };
    audio.onerror = () => {
      URL.revokeObjectURL(audioUrl);
      activeAudioElement = null;
      playBrowserCoachSpeech(processedText, options);
    };

    await audio.play();
  } catch (err) {
    // Zero-downtime graceful fallback to local browser voice
    playBrowserCoachSpeech(processedText, options);
  }
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
