import { useCallback, useEffect, useRef, useState } from "react";
import { joinSpeechSegments, updateSpeechResultSlots, type SpeechResultSnapshot } from "../lib/speechTranscript";

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
  onstart: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;
type VoiceCaptureOptions = {
  autoStopOnSilence?: boolean;
  onAudioLevel?: (level: number) => void;
};

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  }
}

export const isMobileDevice =
  typeof navigator !== "undefined" &&
  /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent || "");

function getSpeechRecognitionAPI(): SpeechRecognitionCtor | undefined {
  return typeof window !== "undefined" ? window.SpeechRecognition || window.webkitSpeechRecognition : undefined;
}

const ERROR_MESSAGES: Record<string, string> = {
  "no-speech": "No speech was detected. Try again or type your message.",
  "audio-capture": "No microphone was found.",
  "not-allowed": "Microphone permission was denied.",
  network: "Speech recognition network error. Try again.",
  aborted: "Listening stopped.",
};

function speechDebugEnabled(): boolean {
  try {
    return window.localStorage.getItem("digidara_speech_debug") === "1";
  } catch {
    return false;
  }
}

/**
 * Robustly merge cumulative speech transcripts.
 * Fixes Android Chrome's cumulative transcription bug where each isFinal event
 * repeats the entire prefix of the utterance.
 */
export function mergeCumulativeText(existing: string, incoming: string): string {
  const a = existing.trim();
  const b = incoming.trim();
  if (!a) return b;
  if (!b) return a;
  if (a === b) return a;
  if (b.toLowerCase().startsWith(a.toLowerCase())) return b;
  if (a.toLowerCase().endsWith(b.toLowerCase())) return a;

  const aWords = a.split(/\s+/);
  const bWords = b.split(/\s+/);
  const maxCheck = Math.min(aWords.length, bWords.length);
  for (let len = maxCheck; len >= 1; len--) {
    const aSuffix = aWords.slice(aWords.length - len).join(" ").toLowerCase();
    const bPrefix = bWords.slice(0, len).join(" ").toLowerCase();
    if (aSuffix === bPrefix) {
      return `${aWords.slice(0, aWords.length - len).join(" ")} ${b}`.trim();
    }
  }

  return joinSpeechSegments([existing, incoming]);
}

/** Browser-only speech-to-text for the chat composer: dictate into the
 * text input instead of typing. Purely client-side (Web Speech API) — the
 * recognized text is sent through the exact same `onSend(text)` path as
 * anything typed, so no backend agent needs to know the difference. */
export default function useSpeechRecognition(locale = "en-US") {
  const [listening, setListening] = useState(false);
  const [error, setError] = useState("");
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const keepListeningRef = useRef(false);
  const vadCleanupRef = useRef<(() => void) | null>(null);
  const retryCountRef = useRef(0);

  const stop = useCallback(() => {
    keepListeningRef.current = false;
    vadCleanupRef.current?.();
    vadCleanupRef.current = null;
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
    (onResult: (text: string, final: boolean) => void, options: VoiceCaptureOptions = {}) => {
      setError("");
      const SpeechRecognitionAPI = getSpeechRecognitionAPI();
      if (!SpeechRecognitionAPI) {
        setError("Voice input isn't supported in this browser — try Chrome or Edge.");
        return false;
      }
      keepListeningRef.current = false;
      retryCountRef.current = 0;
      const previousRecognition = recognitionRef.current;
      recognitionRef.current = null;
      try {
        previousRecognition?.abort();
      } catch {
        // Ignore.
      }

      const recognition = new SpeechRecognitionAPI();
      recognition.lang = locale;
      recognition.interimResults = true;
      recognition.continuous = true;

      let finalText = "";
      let latestText = "";
      let completedSessionsText = "";
      const resultSlots = new Map<number, SpeechResultSnapshot>();

      recognition.onresult = (event) => {
        retryCountRef.current = 0;
        const assembled = updateSpeechResultSlots(resultSlots, event);
        finalText = assembled.finalText;
        latestText = assembled.displayText;
        const runningText = joinSpeechSegments([completedSessionsText, latestText]);
        if (speechDebugEnabled()) {
          console.debug("[DigiDARA speech result]", {
            resultIndex: event.resultIndex,
            results: Array.from(event.results, (result, index) => ({
              index,
              isFinal: result.isFinal,
              transcript: result[0]?.transcript || "",
            })),
            finalText: joinSpeechSegments([completedSessionsText, finalText]),
            interimText: assembled.interimText,
            displayText: runningText,
          });
        }
        onResult(runningText, false);

        // On mobile where getUserMedia is bypassed to prevent hardware mic locking,
        // animate the orb on speech transcript updates:
        if (isMobileDevice && runningText) {
          options.onAudioLevel?.(0.75);
          window.setTimeout(() => options.onAudioLevel?.(0.15), 180);
        }
      };

      recognition.onerror = (event) => {
        if (recognitionRef.current !== recognition) return;

        // Browsers commonly emit no-speech or network hiccups before ending a session.
        // Auto-recover seamlessly while keepListeningRef is active:
        if (
          (event.error === "no-speech" || event.error === "network") &&
          keepListeningRef.current &&
          retryCountRef.current < 5
        ) {
          retryCountRef.current += 1;
          return;
        }

        keepListeningRef.current = false;
        setListening(false);
        setError(ERROR_MESSAGES[event.error] || "Speech recognition stopped unexpectedly.");
      };

      recognition.onstart = () => {
        setListening(true);
        setError("");
        if (speechDebugEnabled()) console.debug("[DigiDARA speech start]", { monotonicMs: Math.round(performance.now()) });
      };

      recognition.onend = () => {
        if (recognitionRef.current !== recognition) return;

        completedSessionsText = joinSpeechSegments([
          completedSessionsText,
          latestText || finalText,
        ]);
        finalText = "";
        latestText = "";
        resultSlots.clear();
        if (speechDebugEnabled()) {
          console.debug("[DigiDARA speech end]", {
            completedText: completedSessionsText,
            restarting: keepListeningRef.current,
          });
        }

        // Mobile Keep-Alive: If active, mobile Chrome killed the session after a short pause.
        // Re-arm immediately so the microphone stays ON during speaking practice!
        if (keepListeningRef.current) {
          window.setTimeout(() => {
            if (!keepListeningRef.current || recognitionRef.current !== recognition) return;
            try {
              recognition.start();
            } catch {
              window.setTimeout(() => {
                if (keepListeningRef.current && recognitionRef.current === recognition) {
                  try {
                    recognition.start();
                  } catch {
                    keepListeningRef.current = false;
                    recognitionRef.current = null;
                    setListening(false);
                    setError("Speech recognition stopped unexpectedly. Restart the microphone or type your answer.");
                  }
                }
              }, 250);
            }
          }, 150);
          return;
        }

        setListening(false);
        vadCleanupRef.current?.();
        vadCleanupRef.current = null;
        recognitionRef.current = null;
        onResult(completedSessionsText.trim(), true);
      };

      recognitionRef.current = recognition;
      keepListeningRef.current = true;
      recognition.start();

      // Desktop-only VAD: On mobile, simultaneous getUserMedia locks/crashes mobile Web Speech API.
      // On desktop, it runs cleanly to provide orb mic-energy level feedback.
      if (!isMobileDevice && options.autoStopOnSilence && navigator.mediaDevices?.getUserMedia && window.AudioContext) {
        let disposed = false;
        let stream: MediaStream | null = null;
        let audioContext: AudioContext | null = null;
        let animationFrame: number | undefined;

        const cleanupVad = () => {
          disposed = true;
          if (animationFrame !== undefined) window.cancelAnimationFrame(animationFrame);
          options.onAudioLevel?.(0);
          stream?.getTracks().forEach((track) => track.stop());
          if (audioContext && audioContext.state !== "closed") void audioContext.close();
          if (vadCleanupRef.current === cleanupVad) vadCleanupRef.current = null;
        };
        vadCleanupRef.current = cleanupVad;

        void navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        }).then((mediaStream) => {
          if (disposed) {
            mediaStream.getTracks().forEach((track) => track.stop());
            return;
          }
          stream = mediaStream;
          audioContext = new AudioContext();
          const source = audioContext.createMediaStreamSource(mediaStream);
          const analyser = audioContext.createAnalyser();
          analyser.fftSize = 1024;
          source.connect(analyser);
          const samples = new Uint8Array(analyser.fftSize);
          let speechDetected = false;
          let quietSince = 0;

          const measure = () => {
            if (disposed) return;
            analyser.getByteTimeDomainData(samples);
            let sum = 0;
            for (const sample of samples) {
              const value = (sample - 128) / 128;
              sum += value * value;
            }
            const rms = Math.sqrt(sum / samples.length);
            const now = performance.now();
            const normalizedLevel = Math.min(1, Math.max(0, (rms - 0.012) * 8.5));
            options.onAudioLevel?.(normalizedLevel);
            if (rms >= 0.015) {
              speechDetected = true;
              quietSince = 0;
              if (typeof window !== "undefined" && window.speechSynthesis?.speaking) {
                window.speechSynthesis.cancel();
              }
            } else if (speechDetected) {
              if (!quietSince) quietSince = now;
              // 12-second silence allowance before VAD stops, coordinating with 6.5s auto-submit:
              if (now - quietSince >= 12000) {
                cleanupVad();
                try {
                  recognitionRef.current?.stop();
                } catch {
                  // Recognition already finished.
                }
                return;
              }
            }
            animationFrame = window.requestAnimationFrame(measure);
          };
          measure();
        }).catch(() => {
          // Keep browser ASR usable when audio analysis is unavailable
        });
      }
      return true;
    },
    [locale],
  );

  return { supported: Boolean(getSpeechRecognitionAPI()), listening, error, start, stop };
}
