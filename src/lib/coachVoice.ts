/**
 * Unified Female Coach Voice and Natural Pacing Engine.
 *
 * Implements Phase 1 of the Coach Voice Architecture:
 * 1. Prioritized female natural English voice selection (Jenny, Aria, Google US English, Samantha, etc.).
 * 2. Conversational cadence and natural pause pre-processing (greeting commas, boundary pauses, question intonation).
 * 3. Consistent teacher pacing (rate ~0.90, pitch ~1.02).
 */

// Priority list for warm, clear female English voices across Edge, Chrome, Safari, Windows, and Mac
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

/**
 * Find the most natural female English voice available on the student's browser/system.
 */
export function selectBestCoachVoice(): SpeechSynthesisVoice | null {
  if (typeof window === "undefined" || !window.speechSynthesis) return null;

  const voices = window.speechSynthesis.getVoices() || [];
  if (!voices.length) return null;

  // 1. Try prioritized natural female voices
  for (const pattern of FEMALE_VOICE_PATTERNS) {
    const match = voices.find((v) => pattern.test(v.name) && v.lang?.startsWith("en"));
    if (match) return match;
  }

  // 2. Try any en-US voice that looks female or natural
  const usFemale = voices.find(
    (v) => (v.lang === "en-US" || v.lang === "en_US") && /female|woman|natural/i.test(v.name)
  );
  if (usFemale) return usFemale;

  // 3. Any en-US voice
  const usVoice = voices.find((v) => v.lang === "en-US" || v.lang === "en_US");
  if (usVoice) return usVoice;

  // 4. Any English voice
  const anyEnglish = voices.find((v) => v.lang?.toLowerCase().startsWith("en"));
  if (anyEnglish) return anyEnglish;

  return voices[0] || null;
}

/**
 * Pre-process text to insert natural conversational pauses and teacher cadence.
 *
 * Examples:
 * - "Good morning Harini what did you do today"
 *   -> "Good morning, Harini. What did you do today?"
 * - Handles punctuation so the browser synthesizer pauses at greetings and clause boundaries.
 */
export function formatCoachSpeechText(rawText: string): string {
  if (!rawText) return "";

  let text = rawText.trim();

  // 1. Ensure comma after greetings like "Good morning Harini", "Hello Harini", "Hi Harini"
  text = text.replace(
    /^(Good\s+(?:morning|afternoon|evening)|Hello|Hi|Hey)\s+([A-Z][a-zA-Z]+)(?=[,\s.!?]|$)/i,
    "$1, $2."
  );

  // 2. Ensure greeting questions have proper punctuation boundary
  // e.g. "Good morning, Harini! What did you do today" -> "Good morning, Harini. What did you do today?"
  text = text.replace(/([.!?])\s*([A-Z])/g, "$1 $2");

  // 3. Ensure trailing question mark if sentence starts with question words
  if (/^(what|how|why|when|where|who|which|can|could|would|are|is|do|did|have|has)\b/i.test(text) && !/[.!?]$/.test(text)) {
    text = `${text}?`;
  } else if (!/[.!?]$/.test(text)) {
    text = `${text}.`;
  }

  // 4. Replace ellipsis or harsh symbols with gentle conversational pause points
  text = text.replace(/\.{2,}/g, ", ");
  text = text.replace(/[—–]/g, ", ");

  return text;
}

export interface CoachUtteranceOptions {
  rate?: number;
  pitch?: number;
  volume?: number;
  onStart?: () => void;
  onEnd?: () => void;
  onError?: (e: SpeechSynthesisErrorEvent) => void;
}

/**
 * Create a SpeechSynthesisUtterance configured with optimal teacher parameters.
 */
export function createCoachUtterance(text: string, options: CoachUtteranceOptions = {}): SpeechSynthesisUtterance {
  const processedText = formatCoachSpeechText(text);
  const utterance = new SpeechSynthesisUtterance(processedText);

  // Calibrated natural teacher pacing
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
