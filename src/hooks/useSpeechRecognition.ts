import { useCallback, useEffect, useRef, useState } from "react";

/** Minimal ambient typing for the Web Speech API — not in TS's default DOM
 * lib, and only Chrome/Edge/Safari expose it (Firefox does not), always
 * under the `webkit`-prefixed name in Safari/Chromium. */
interface SpeechRecognitionResultLike {
  isFinal: boolean;
  0: { transcript: string; confidence: number };
}
interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: ArrayLike<SpeechRecognitionResultLike>;
}
interface SpeechRecognitionErrorEventLike {
  error: string;
}
interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  }
}

const SpeechRecognitionAPI: SpeechRecognitionCtor | undefined =
  typeof window !== "undefined" ? window.SpeechRecognition || window.webkitSpeechRecognition : undefined;

const ERROR_MESSAGES: Record<string, string> = {
  "no-speech": "No speech was detected. Try again or type your message.",
  "audio-capture": "No microphone was found.",
  "not-allowed": "Microphone permission was denied.",
  network: "Speech recognition network error. Try again.",
  aborted: "Listening stopped.",
};

/** Browser-only speech-to-text for the chat composer: dictate into the
 * text input instead of typing. Purely client-side (Web Speech API) — the
 * recognized text is sent through the exact same `onSend(text)` path as
 * anything typed, so no backend agent needs to know the difference. */
export default function useSpeechRecognition(locale = "en-US") {
  const [listening, setListening] = useState(false);
  const [error, setError] = useState("");
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  const stop = useCallback(() => {
    try {
      recognitionRef.current?.stop();
    } catch {
      // Already stopped — ignore.
    }
  }, []);

  useEffect(() => stop, [stop]);

  /** Starts listening. `onResult` is called with the running transcript
   * (accumulated final text + the current interim guess) on every update,
   * and once more with `final: true` when recognition ends. */
  const start = useCallback(
    (onResult: (text: string, final: boolean) => void) => {
      setError("");
      if (!SpeechRecognitionAPI) {
        setError("Voice input isn't supported in this browser — try Chrome or Edge.");
        return false;
      }
      try {
        recognitionRef.current?.abort();
      } catch {
        // Ignore.
      }

      const recognition = new SpeechRecognitionAPI();
      recognition.lang = locale;
      recognition.interimResults = true;
      recognition.continuous = true;

      let finalText = "";
      recognition.onresult = (event) => {
        let interimText = "";
        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const result = event.results[i];
          const text = result[0]?.transcript || "";
          if (result.isFinal) finalText = `${finalText} ${text}`.trim();
          else interimText += text;
        }
        onResult(`${finalText} ${interimText}`.trim(), false);
      };
      recognition.onerror = (event) => {
        setError(ERROR_MESSAGES[event.error] || "Speech recognition stopped unexpectedly.");
      };
      recognition.onend = () => {
        setListening(false);
        recognitionRef.current = null;
        onResult(finalText.trim(), true);
      };

      recognitionRef.current = recognition;
      setListening(true);
      recognition.start();
      return true;
    },
    [locale],
  );

  return { supported: Boolean(SpeechRecognitionAPI), listening, error, start, stop };
}
