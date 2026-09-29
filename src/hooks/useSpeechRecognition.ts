import { useCallback, useEffect, useRef, useState } from "react";

/** Minimal ambient typing for the Web Speech API */
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

const SpeechRecognitionAPI: SpeechRecognitionCtor | undefined =
  typeof window !== "undefined" ? window.SpeechRecognition || window.webkitSpeechRecognition : undefined;

export const isMobileDevice =
  typeof navigator !== "undefined" &&
  /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent || "");

const ERROR_MESSAGES: Record<string, string> = {
  "no-speech": "No speech was detected. Try again or type your message.",
  "audio-capture": "No microphone was found.",
  "not-allowed": "Microphone permission was denied.",
  network: "Speech recognition network error. Try again.",
  aborted: "Listening stopped.",
};

/**
 * Robustly merge cumulative speech transcripts.
 * Fixes Android Chrome's cumulative transcription bug where each isFinal event
 * repeats the entire prefix of the utterance (e.g. "MNC" -> "MNC anything" -> "MNC anything can you").
 */
export function mergeCumulativeText(existing: string, incoming: string): string {
  const a = existing.trim();
  const b = incoming.trim();
  if (!a) return b;
  if (!b) return a;
  if (a === b) return a;

  // If incoming already starts with existing, incoming is the fuller accumulated sentence
  if (b.toLowerCase().startsWith(a.toLowerCase())) return b;

  // If existing already ends with incoming, no need to append
  if (a.toLowerCase().endsWith(b.toLowerCase())) return a;

  // Check for word-level overlap at the boundary
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

  return `${a} ${b}`.trim();
}

/**
 * Mobile-resilient browser speech-to-text hook.
 * Handles mobile Android/iOS keep-alive, audio lock contention, and cumulative deduplication.
 */
export default function useSpeechRecognition(locale = "en-US") {
  const [listening, setListening] = useState(false);
  const [error, setError] = useState("");
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const vadCleanupRef = useRef<(() => void) | null>(null);
  const activeSessionRef = useRef(false);
  const reconnectTimerRef = useRef<number | undefined>(undefined);
  const sessionDataRef = useRef<{
    onResult: (text: string, final: boolean) => void;
    options: VoiceCaptureOptions;
    finalText: string;
    latestText: string;
  } | null>(null);

  const stop = useCallback(() => {
    activeSessionRef.current = false;
    window.clearTimeout(reconnectTimerRef.current);
    sessionDataRef.current = null;
    vadCleanupRef.current?.();
    vadCleanupRef.current = null;
    try {
      recognitionRef.current?.stop();
    } catch {
      // Already stopped — ignore.
    }
    setListening(false);
  }, []);

  useEffect(() => stop, [stop]);

  const launchRecognition = useCallback(() => {
    if (!activeSessionRef.current || !sessionDataRef.current || !SpeechRecognitionAPI) return;

    try {
      recognitionRef.current?.abort();
    } catch {
      // Ignore
    }

    const currentSession = sessionDataRef.current;
    const recognition = new SpeechRecognitionAPI();
    recognition.lang = locale;
    recognition.interimResults = true;
    recognition.continuous = true;

    recognition.onresult = (event) => {
      if (!sessionDataRef.current) return;

      // Extract fresh finals and interims from this event batch
      let batchFinal = "";
      let batchInterim = "";

      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const text = result[0]?.transcript || "";
        if (result.isFinal) {
          batchFinal = mergeCumulativeText(batchFinal, text);
        } else {
          batchInterim = text;
        }
      }

      if (batchFinal) {
        sessionDataRef.current.finalText = mergeCumulativeText(sessionDataRef.current.finalText, batchFinal);
      }

      const composite = `${sessionDataRef.current.finalText} ${batchInterim}`.trim();
      sessionDataRef.current.latestText = composite;
      currentSession.onResult(composite, false);

      // On mobile where getUserMedia is bypassed, animate voice level on transcript activity
      if (isMobileDevice && composite) {
        currentSession.options.onAudioLevel?.(0.75);
        window.setTimeout(() => currentSession.options.onAudioLevel?.(0.15), 180);
      }
    };

    recognition.onerror = (event) => {
      if (!activeSessionRef.current) return;
      if (event.error === "aborted") return;

      // Auto-recover from transient errors without killing the session or showing red errors
      if (
        event.error === "network" ||
        event.error === "no-speech" ||
        (isMobileDevice && (event.error === "audio-capture" || event.error === "bad-grammar"))
      ) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = window.setTimeout(() => {
          if (activeSessionRef.current) {
            launchRecognition();
          }
        }, 300);
        return;
      }

      // Explicit permission denials
      if (event.error === "not-allowed") {
        activeSessionRef.current = false;
        setListening(false);
        setError(ERROR_MESSAGES["not-allowed"]);
      }
    };

    recognition.onstart = () => {
      setListening(true);
      setError("");
    };

    recognition.onend = () => {
      // Mobile Keep-Alive: If session is still active, mobile Chrome killed the session after a brief silence.
      // Re-arm immediately so the microphone NEVER turns OFF during speaking practice!
      if (activeSessionRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = window.setTimeout(() => {
          if (activeSessionRef.current) {
            launchRecognition();
          }
        }, isMobileDevice ? 150 : 250);
        return;
      }

      // Session ended intentionally
      vadCleanupRef.current?.();
      vadCleanupRef.current = null;
      setListening(false);
      recognitionRef.current = null;
      const data = sessionDataRef.current;
      if (data) {
        currentSession.onResult((data.finalText.trim() || data.latestText).trim(), true);
      }
    };

    recognitionRef.current = recognition;
    try {
      recognition.start();
    } catch {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = window.setTimeout(() => {
        if (activeSessionRef.current) launchRecognition();
      }, 250);
    }
  }, [locale]);

  const start = useCallback(
    (onResult: (text: string, final: boolean) => void, options: VoiceCaptureOptions = {}) => {
      setError("");
      if (!SpeechRecognitionAPI) {
        setError("Voice input isn't supported in this browser — try Chrome or Edge.");
        return false;
      }

      activeSessionRef.current = true;
      sessionDataRef.current = {
        onResult,
        options,
        finalText: "",
        latestText: "",
      };

      launchRecognition();

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
    [launchRecognition],
  );

  return { supported: Boolean(SpeechRecognitionAPI), listening, error, start, stop };
}
