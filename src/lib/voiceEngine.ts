/**
 * Natural voice for every agent: warm, friendly speech in English, Tamil or
 * both (orchestrator POST /voice/speak), the way ChatGPT and Gemini voice
 * sound rather than a flat reading voice.
 *
 * Speed: the reply is split into sentence-sized chunks. The first chunk is
 * requested at once and plays as soon as it arrives, while the next one is
 * already being fetched, so speech starts after one sentence, not after the
 * whole reply. Every agent on every device speaks with the same voice (Nila,
 * a friendly Indian coach). Only if it cannot be reached at all (offline, no
 * points) does the device's Indian voice continue from the same point -- a
 * Tamil voice for Tamil text when the device has one.
 */
import { speakableText, splitForSpeech } from "./voiceText";
import { loadVoicePrefs, voiceLanguagePreference, type VoicePrefs } from "./voicePrefs";
import { sessionToken } from "./session";
import { pickIndianVoice } from "./indianVoice";

export { pickIndianVoice };

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

/** One retry on a failed chunk, so a brief network blip does not switch the
 * learner to a different (device) voice halfway through a reply. */
async function fetchChunk(text: string, prefs: VoicePrefs): Promise<Blob> {
  try {
    return await fetchChunkOnce(text, prefs);
  } catch (error) {
    if (error instanceof Error && /voice (401|402|403|503)/.test(error.message)) throw error;
    return fetchChunkOnce(text, prefs);
  }
}

async function fetchChunkOnce(text: string, prefs: VoicePrefs): Promise<Blob> {
  const token = sessionToken() || "";
  const response = await fetch(`${BASE}/voice/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ text, language: prefs.language, persona: prefs.persona }),
  });
  if (!response.ok) throw new Error(`voice ${response.status}`);
  return response.blob();
}

/**
 * Louder speech: the voice plays through a compressor and a gain boost, so it
 * is clearly audible on phone and laptop speakers without distorting. The
 * audio context only exists once the learner has tapped or typed (browsers
 * keep it silent before that); until then the voice plays at normal volume.
 */
const VOICE_GAIN = 1.9;
let boostContext: AudioContext | null = null;

function audioContextCtor(): typeof AudioContext | undefined {
  if (typeof window === "undefined") return undefined;
  return window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
}

function unlockVoiceBoost(): void {
  const Ctor = audioContextCtor();
  if (!Ctor) return;
  try {
    boostContext ??= new Ctor();
    if (boostContext.state !== "running") void boostContext.resume();
  } catch {
    boostContext = null;
  }
}

if (typeof document !== "undefined") {
  for (const type of ["pointerdown", "keydown", "touchstart"]) {
    document.addEventListener(type, unlockVoiceBoost, { capture: true, passive: true });
  }
}

function boost(audio: HTMLAudioElement): void {
  audio.volume = 1;
  const context = boostContext;
  // A suspended context would mute the voice instead of boosting it.
  if (!context || context.state !== "running") return;
  try {
    const source = context.createMediaElementSource(audio);
    const compressor = context.createDynamicsCompressor();
    compressor.threshold.value = -24;
    compressor.knee.value = 12;
    compressor.ratio.value = 4;
    compressor.attack.value = 0.003;
    compressor.release.value = 0.25;
    const gain = context.createGain();
    gain.gain.value = VOICE_GAIN;
    source.connect(compressor).connect(gain).connect(context.destination);
  } catch {
    // Plays at normal volume.
  }
}

function playBlob(blob: Blob, prefs: VoicePrefs, mySession: number, onFirstPlay: () => void): Promise<void> {
  return new Promise((resolve, reject) => {
    if (mySession !== session) return resolve();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.playbackRate = prefs.speed;
    boost(audio);
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
      const voice = pickIndianVoice(lang);
      if (voice) utterance.voice = voice;
      utterance.lang = voice?.lang || (lang === "ta" ? "ta-IN" : "en-IN");
      // A little slower than the device default, so every student can follow.
      utterance.rate = Math.min(1.3, Math.max(0.7, prefs.speed * 0.9));
      utterance.pitch = 1;
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
      {
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
