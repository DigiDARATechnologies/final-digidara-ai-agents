/**
 * Natural voice for every agent: warm, friendly speech in English, Tamil or
 * both (orchestrator POST /voice/speak), the way ChatGPT and Gemini voice
 * sound rather than a flat reading voice.
 *
 * Speed: the reply is split into sentence-sized chunks. The first chunk is
 * requested at once and plays as soon as it arrives, while the next one is
 * already being fetched, so speech starts after one sentence, not after the
 * whole reply. If natural voice is unavailable (offline, no points, server
 * error), the browser's own voice continues from the same point -- a Tamil
 * voice for Tamil text when the device has one.
 */
import { speakableText, splitForSpeech } from "./voiceText";
import { loadVoicePrefs, voiceLanguagePreference, type VoicePrefs } from "./voicePrefs";

export interface SpeakHandlers {
  onStart?: () => void;
  onEnd?: () => void;
  onError?: (error?: unknown) => void;
}

const BASE = (() => {
  const raw = import.meta.env.VITE_GATEWAY_API_URL !== undefined ? String(import.meta.env.VITE_GATEWAY_API_URL) : "http://127.0.0.1:8100";
  return raw.endsWith("/") ? raw.slice(0, -1) : raw;
})();

const TAMIL = /[஀-௿]/;

let session = 0;
let activeAudio: HTMLAudioElement | null = null;
let speaking = false;

export function isSpeaking(): boolean {
  return speaking;
}

/** Stop whatever is being said now (natural or browser voice). */
export function stopSpeaking(): void {
  session += 1;
  speaking = false;
  if (activeAudio) {
    try {
      activeAudio.pause();
      activeAudio.src = "";
    } catch {
      // Already stopped.
    }
    activeAudio = null;
  }
  if (typeof window !== "undefined" && window.speechSynthesis) {
    try {
      window.speechSynthesis.cancel();
    } catch {
      // Nothing was speaking.
    }
  }
}

async function fetchChunk(text: string, prefs: VoicePrefs): Promise<Blob> {
  const token = localStorage.getItem("digidara_token") || "";
  const response = await fetch(`${BASE}/voice/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ text, language: prefs.language, persona: prefs.persona }),
  });
  if (!response.ok) throw new Error(`voice ${response.status}`);
  return response.blob();
}

function playBlob(blob: Blob, prefs: VoicePrefs, mySession: number, onFirstPlay: () => void): Promise<void> {
  return new Promise((resolve, reject) => {
    if (mySession !== session) return resolve();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.playbackRate = prefs.speed;
    activeAudio = audio;
    const finish = (error?: unknown) => {
      URL.revokeObjectURL(url);
      if (activeAudio === audio) activeAudio = null;
      if (error) reject(error);
      else resolve();
    };
    audio.onplaying = onFirstPlay;
    audio.onended = () => finish();
    audio.onerror = () => finish(new Error("audio playback failed"));
    audio.play().catch(finish);
  });
}

function pickBrowserVoice(lang: "ta" | "en"): SpeechSynthesisVoice | null {
  const voices = window.speechSynthesis?.getVoices() ?? [];
  if (lang === "ta") return voices.find((v) => v.lang?.toLowerCase().startsWith("ta")) ?? null;
  const preferred = [/Natural/i, /Google UK English Female/i, /Google US English/i, /Microsoft (Neerja|Heera|Jenny|Aria)/i];
  for (const pattern of preferred) {
    const voice = voices.find((v) => pattern.test(v.name) && v.lang?.toLowerCase().startsWith("en"));
    if (voice) return voice;
  }
  return voices.find((v) => v.lang === "en-IN") ?? voices.find((v) => v.lang?.startsWith("en")) ?? null;
}

function browserSpeak(chunks: string[], prefs: VoicePrefs, mySession: number, onFirstPlay: () => void): Promise<void> {
  return new Promise((resolve) => {
    const synthesis = typeof window !== "undefined" ? window.speechSynthesis : undefined;
    if (!synthesis || !chunks.length) return resolve();
    let index = 0;
    const next = () => {
      if (mySession !== session || index >= chunks.length) return resolve();
      const text = chunks[index++];
      const lang = TAMIL.test(text) ? "ta" : "en";
      const utterance = new SpeechSynthesisUtterance(text);
      const voice = pickBrowserVoice(lang);
      if (voice) utterance.voice = voice;
      utterance.lang = voice?.lang || (lang === "ta" ? "ta-IN" : "en-IN");
      utterance.rate = Math.min(1.4, Math.max(0.7, prefs.speed * 0.96));
      utterance.pitch = 1.03;
      utterance.onstart = onFirstPlay;
      utterance.onend = next;
      utterance.onerror = next;
      synthesis.speak(utterance);
    };
    next();
  });
}

/**
 * Speak `text` naturally. Resolves `true` once speech has been started (it
 * keeps playing afterwards), `false` if voice is off or there is nothing to
 * say. onEnd fires exactly once, when everything has been said or stopped.
 * `force`: the learner asked for it (Listen, Preview), so speak even when
 * "Speak replies" is switched off.
 */
export async function speakNatural(text: string, handlers: SpeakHandlers = {}, force = false): Promise<boolean> {
  stopSpeaking();
  const prefs = loadVoicePrefs();
  const chunks = splitForSpeech(speakableText(text));
  if ((!prefs.enabled && !force) || !chunks.length) {
    handlers.onEnd?.();
    return false;
  }
  const mySession = session;
  speaking = true;
  let started = false;
  let ended = false;
  const onFirstPlay = () => {
    if (!started) {
      started = true;
      handlers.onStart?.();
    }
  };
  const finish = (error?: unknown) => {
    if (ended) return;
    ended = true;
    if (mySession === session) speaking = false;
    if (error) handlers.onError?.(error);
    handlers.onEnd?.();
  };

  let resolveStarted: (value: boolean) => void = () => {};
  const startedPromise = new Promise<boolean>((resolve) => { resolveStarted = resolve; });
  const markStarted = () => { onFirstPlay(); resolveStarted(true); };

  void (async () => {
    let index = 0;
    try {
      if (prefs.mode === "natural") {
        let pending: Promise<Blob> | null = fetchChunk(chunks[0], prefs);
        while (pending && mySession === session) {
          const blob: Blob = await pending;
          const next = index + 1;
          // Fetch the next chunk while this one plays.
          pending = next < chunks.length ? fetchChunk(chunks[next], prefs) : null;
          pending?.catch(() => undefined);
          await playBlob(blob, prefs, mySession, markStarted);
          // Only a chunk that was actually heard is skipped by the fallback.
          index = next;
        }
      }
    } catch {
      // Natural voice failed: the browser voice says the rest.
    }
    if (mySession === session && index < chunks.length) {
      await browserSpeak(chunks.slice(index), prefs, mySession, markStarted);
    }
    resolveStarted(started);
    finish();
  })();

  return startedPromise;
}

/** For the voice settings' Preview button. */
export function previewVoice(handlers: SpeakHandlers = {}): Promise<boolean> {
  const language = voiceLanguagePreference();
  const sample = language === "ta"
    ? "வணக்கம்! நான் உங்கள் DigiDARA பயிற்சியாளர். இன்று interview-க்கு சேர்ந்து தயார் ஆகலாமா?"
    : "Hi! I'm your DigiDARA coach. Shall we get you interview-ready today?";
  return speakNatural(sample, handlers, true);
}
