/**
 * "Hey Boss": a listener that waits for the wake words and hands over what was
 * said after them. It uses the browser's own speech recognition, so nothing is
 * recorded or sent anywhere until the wake words are heard; after that Boss
 * opens and the normal voice conversation takes over. Browsers that have no
 * speech recognition (some phones) simply have no wake word: the Boss button
 * and its microphone still work there.
 */

// Recognisers often hear "hey boss" as "hey bus" or "hey bos".
const WAKE = /\b(?:hey|hi|hello|ok|okay|a)\s*,?\s*(?:boss|bos|bus)\b[\s,.!?:-]*/i;

/** The words after "Hey Boss" in what was heard ("" if only the wake words), or null if they were not said. */
export function matchWake(transcript: string): { rest: string } | null {
  const match = WAKE.exec(transcript);
  if (!match) return null;
  return { rest: transcript.slice(match.index + match[0].length).trim() };
}

interface RecognitionResultLike { isFinal: boolean; 0: { transcript: string } }
interface RecognitionEventLike { resultIndex: number; results: ArrayLike<RecognitionResultLike> }
interface RecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: RecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: ((event: { error?: string }) => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

function recognitionConstructor(): (new () => RecognitionLike) | undefined {
  if (typeof window === "undefined") return undefined;
  const w = window as unknown as { SpeechRecognition?: new () => RecognitionLike; webkitSpeechRecognition?: new () => RecognitionLike };
  return w.SpeechRecognition || w.webkitSpeechRecognition;
}

export function wakeWordSupported(): boolean {
  return Boolean(recognitionConstructor());
}

// After the wake words, wait this long for the rest of the sentence.
const REST_WAIT_MS = 1_200;

/** Starts listening for the wake words. `onWake` gets the words said after
 * them (possibly ""), once, and the listener then stops. Returns stop. */
export function listenForWakeWord(onWake: (rest: string) => void, lang = "en-IN"): () => void {
  const Recognition = recognitionConstructor();
  if (!Recognition) return () => {};
  let stopped = false;
  let woke = false;
  let timer: number | undefined;
  let restartTimer: number | undefined;
  let recognition: RecognitionLike | null = null;

  const fire = (rest: string) => {
    if (woke || stopped) return;
    woke = true;
    stop();
    onWake(rest);
  };

  function begin() {
    if (stopped) return;
    recognition = new Recognition!();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = lang;
    recognition.onresult = (event) => {
      let heard = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) heard += `${event.results[i][0].transcript} `;
      const wake = matchWake(heard);
      if (!wake) return;
      const final = event.results[event.results.length - 1].isFinal;
      window.clearTimeout(timer);
      if (final) fire(wake.rest);
      else timer = window.setTimeout(() => fire(wake.rest), REST_WAIT_MS);
    };
    recognition.onerror = (event) => {
      // No permission, or no service: stop trying rather than looping.
      if (event.error === "not-allowed" || event.error === "service-not-allowed") stopped = true;
    };
    recognition.onend = () => {
      // The browser ends a continuous session now and then: start again.
      if (!stopped && !woke) restartTimer = window.setTimeout(begin, 300);
    };
    try {
      recognition.start();
    } catch {
      restartTimer = window.setTimeout(begin, 1_000);
    }
  }

  function stop() {
    stopped = true;
    window.clearTimeout(timer);
    window.clearTimeout(restartTimer);
    try {
      recognition?.abort();
    } catch {
      // Already stopped.
    }
    recognition = null;
  }

  begin();
  return stop;
}
