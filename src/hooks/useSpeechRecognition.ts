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
  const vadCleanupRef = useRef<(() => void) | null>(null);

  const stop = useCallback(() => {
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
      // Short utterances can remain interim when recording ends. Keep the
      // latest text so stopping does not clear a usable one-word result.
      let latestText = "";
      recognition.onresult = (event) => {
        let interimText = "";
        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const result = event.results[i];
          const text = result[0]?.transcript || "";
          if (result.isFinal) finalText = `${finalText} ${text}`.trim();
          else interimText += text;
        }
        latestText = `${finalText} ${interimText}`.trim();
        onResult(latestText, false);
      };
      recognition.onerror = (event) => {
        setError(ERROR_MESSAGES[event.error] || "Speech recognition stopped unexpectedly.");
      };
      recognition.onend = () => {
        vadCleanupRef.current?.();
        vadCleanupRef.current = null;
        setListening(false);
        recognitionRef.current = null;
        onResult((finalText.trim() || latestText).trim(), true);
      };

      recognitionRef.current = recognition;
      setListening(true);
      recognition.start();

      if (options.autoStopOnSilence && navigator.mediaDevices?.getUserMedia && window.AudioContext) {
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

        // Web Speech provides transcription, but it does not expose voice
        // activity. Measure microphone energy separately so a short word can
        // be captured and the recording ends naturally after silence.
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
              if (now - quietSince >= 7000) {
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
          // Keep browser ASR usable when audio analysis is unavailable; the
          // learner can still stop recording manually.
        });
      }
      return true;
    },
    [locale],
  );

  return { supported: Boolean(SpeechRecognitionAPI), listening, error, start, stop };
}
