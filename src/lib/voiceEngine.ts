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
  activeAudio = null;
  for (const audio of [...liveAudio]) release(audio);
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

// Every downloading or playing voice element, so stopSpeaking() silences them all.
const liveAudio = new Set<HTMLAudioElement>();
// Turned off when the server has no streaming voice (an older deploy): the
// whole-sentence /voice/speak is used instead.
let streamingAvailable = true;

function release(audio: HTMLAudioElement | null): void {
  if (!audio) return;
  liveAudio.delete(audio);
  try {
    audio.pause();
    const url = audio.dataset.blobUrl;
    audio.removeAttribute("src");
    audio.load();
    if (url) URL.revokeObjectURL(url);
  } catch {
    // Already released.
  }
}

/** A one-use link the audio element streams the voice from: it starts
 * playing as soon as the first words are generated. */
async function ticketUrl(text: string, prefs: VoicePrefs): Promise<string> {
  const token = sessionToken() || "";
  const response = await fetch(`${BASE}/voice/ticket`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ text, language: prefs.language }),
  });
  if (!response.ok) throw new Error(`voice ${response.status}`);
  const body = (await response.json()) as { url: string };
  return `${BASE}${body.url}`;
}

function audioElement(src: string, prefs: VoicePrefs, blobUrl = false): HTMLAudioElement {
  const audio = new Audio();
  audio.preload = "auto";
  if (blobUrl) audio.dataset.blobUrl = src;
  else if (typeof window !== "undefined" && /^https?:/i.test(src) && !src.startsWith(window.location.origin)) {
    // The API on another origin (local development): needed for the boost.
    audio.crossOrigin = "anonymous";
  }
  audio.src = src;
  audio.playbackRate = prefs.speed;
  boost(audio);
  liveAudio.add(audio);
  return audio;
}

/** The natural voice for one piece of text, already downloading; null when
 * it cannot be reached (the device voice then says that piece). */
async function prepareVoice(text: string, prefs: VoicePrefs): Promise<HTMLAudioElement | null> {
  if (streamingAvailable) {
    try {
      return audioElement(await ticketUrl(text, prefs), prefs);
    } catch (error) {
      const message = error instanceof Error ? error.message : "";
      if (/voice (404|405)/.test(message)) streamingAvailable = false;
      else if (/voice (401|402|403|503)/.test(message)) return null;
    }
  }
  try {
    return audioElement(URL.createObjectURL(await fetchChunk(text, prefs)), prefs, true);
  } catch {
    return null;
  }
}

function playAudio(audio: HTMLAudioElement, prefs: VoicePrefs, onFirstPlay: () => void): Promise<void> {
  return new Promise((resolve, reject) => {
    activeAudio = audio;
    const finish = (error?: unknown) => {
      if (activeAudio === audio) activeAudio = null;
      release(audio);
      if (error) reject(error);
      else resolve();
    };
    audio.onplaying = () => {
      audio.playbackRate = prefs.speed;
      onFirstPlay();
    };
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

export interface SpeechQueue {
  /** Add text to say after what is already queued (a reply as it streams in). */
  push(text: string): void;
  /** Nothing more will be added: onEnd fires once everything has been said. */
  end(): void;
  /** Resolves true once speech has started, false if nothing was said. */
  started: Promise<boolean>;
}

/**
 * Speaks pieces of text one after another as they are added, in the natural
 * voice. Each piece's audio is already downloading while the one before it
 * plays, and plays while it is still being generated, so there is no pause
 * between sentences and the first words come quickly. Replaces anything being
 * said now; onEnd fires exactly once (also when stopped).
 */
export function createSpeechQueue(handlers: SpeakHandlers = {}, force = false): SpeechQueue {
  stopSpeaking();
  const prefs = loadVoicePrefs();
  const enabled = prefs.enabled || force;
  const mySession = session;
  const texts: string[] = [];
  const prepared: Promise<HTMLAudioElement | null>[] = [];
  let closed = false;
  let running = false;
  let started = false;
  let ended = false;
  const waker: { wake: (() => void) | null } = { wake: null };
  let resolveStarted: (value: boolean) => void = () => {};
  const startedPromise = new Promise<boolean>((resolve) => { resolveStarted = resolve; });

  const markStarted = () => {
    if (started) return;
    started = true;
    handlers.onStart?.();
    resolveStarted(true);
  };
  const finish = () => {
    if (ended) return;
    ended = true;
    if (mySession === session) speaking = false;
    resolveStarted(started);
    handlers.onEnd?.();
  };
  const prepare = (index: number) => {
    if (index < texts.length && !prepared[index]) prepared[index] = prepareVoice(texts[index], prefs);
  };

  const run = async () => {
    running = true;
    speaking = true;
    let index = 0;
    while (mySession === session) {
      if (index >= texts.length) {
        if (closed) break;
        await new Promise<void>((resolve) => { waker.wake = resolve; });
        waker.wake = null;
        continue;
      }
      prepare(index);
      const audio = await prepared[index];
      if (mySession !== session) {
        release(audio);
        break;
      }
      // The next piece downloads (and is generated) while this one plays.
      prepare(index + 1);
      let heard = false;
      if (audio) {
        try {
          await playAudio(audio, prefs, markStarted);
          heard = true;
        } catch {
          // Natural voice failed for this piece: the device voice says it.
        }
      }
      if (!heard && mySession === session) await browserSpeak([texts[index]], prefs, mySession, markStarted);
      index += 1;
    }
    for (const pending of prepared.slice(index)) void pending?.then(release);
    finish();
  };

  return {
    started: startedPromise,
    push(text: string) {
      if (!enabled || closed || ended) return;
      const pieces = splitForSpeech(speakableText(text));
      if (!pieces.length) return;
      texts.push(...pieces);
      if (!running) void run();
      waker.wake?.();
    },
    end() {
      closed = true;
      if (!running) finish();
      waker.wake?.();
    },
  };
}

/**
 * Speak `text` naturally. Resolves `true` once speech has been started (it
 * keeps playing afterwards), `false` if voice is off or there is nothing to
 * say. onEnd fires exactly once, when everything has been said or stopped.
 * `force`: the learner asked for it (Listen, Preview), so speak even when
 * "Speak replies" is switched off.
 */
export async function speakNatural(text: string, handlers: SpeakHandlers = {}, force = false): Promise<boolean> {
  const queue = createSpeechQueue(handlers, force);
  queue.push(text);
  queue.end();
  return queue.started;
}

/** For the voice settings' Preview button. */
export function previewVoice(handlers: SpeakHandlers = {}): Promise<boolean> {
  const language = voiceLanguagePreference();
  const sample = language === "ta"
    ? "வணக்கம்! நான் உங்கள் DigiDARA பயிற்சியாளர். இன்று interview-க்கு சேர்ந்து தயார் ஆகலாமா?"
    : "Hi! I'm your DigiDARA coach. Shall we get you interview-ready today?";
  return speakNatural(sample, handlers, true);
}
