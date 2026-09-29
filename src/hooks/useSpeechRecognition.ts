import { useCallback, useEffect, useRef, useState } from "react";
import { joinSpeechSegments, updateSpeechResultSlots, type SpeechResultSnapshot } from "../lib/speechTranscript";
import {
  audioRecordingSupported,
  isMobileVoiceDevice,
  microphoneErrorMessage,
  preferredRecordingType,
} from "../lib/voiceCapture";

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
  /** How long a pause (after some speech) ends the recording. Default 7s. */
  silenceMs?: number;
  /** Recording mode: whole seconds left before a pause ends the recording
   * (only in its last 3 seconds), or null once speech resumes. */
  onSilenceCountdown?: (seconds: number | null) => void;
};

/** Sends a recorded answer to the server and resolves with its transcript. */
export type AudioTranscriber = (audio: Blob) => Promise<string>;

/** Longest single recording on a phone, so an uploaded answer stays small. */
const MAX_RECORDING_MS = 3 * 60 * 1000;
const DEFAULT_SILENCE_MS = 7000;

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  }
}

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

/** Speech-to-text for the chat composer: dictate into the text input
 * instead of typing. The recognized text is sent through the exact same
 * `onSend(text)` path as anything typed.
 *
 * Two ways of getting there:
 * - Desktop (and any agent without a `transcribe` function): the browser's
 *   live Web Speech recognition, words appearing as they are spoken.
 * - Phones, when `transcribe` is given: record the answer on a single
 *   microphone stream and have the server transcribe it when recording
 *   stops. Live recognition is unreliable on phones -- see voiceCapture.ts. */
export default function useSpeechRecognition(locale = "en-US", transcribe?: AudioTranscriber) {
  const [listening, setListening] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [error, setError] = useState("");
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const keepListeningRef = useRef(false);
  const vadCleanupRef = useRef<(() => void) | null>(null);
  const transcribeRef = useRef(transcribe);
  transcribeRef.current = transcribe;
  const recordingMode = Boolean(transcribe) && isMobileVoiceDevice() && audioRecordingSupported();
  // Recording mode: every start() is a new session; finishing an older one is ignored.
  const recordSessionRef = useRef(0);
  const finishRecordingRef = useRef<((deliver: boolean) => void) | null>(null);

  /** Recording mode only: ends the current recording. `deliver` transcribes it
   * and reports the text; otherwise it is thrown away (unmount, restart). */
  const endRecording = useCallback((deliver: boolean) => {
    const finish = finishRecordingRef.current;
    if (finish) {
      finish(deliver);
      return;
    }
    // Still waiting for the microphone to open: cancel that start.
    recordSessionRef.current += 1;
    setListening(false);
  }, []);

  const stop = useCallback(() => {
    if (finishRecordingRef.current) {
      endRecording(true);
      return;
    }
    keepListeningRef.current = false;
    vadCleanupRef.current?.();
    vadCleanupRef.current = null;
    try {
      recognitionRef.current?.stop();
    } catch {
      // Already stopped — ignore.
    }
  }, []);

  useEffect(() => () => {
    endRecording(false);
    stop();
  }, [endRecording, stop]);

  /** Recording mode: one microphone stream feeds both the recorder and the
   * silence detector, so nothing competes for the microphone. */
  const startRecording = useCallback(
    (onResult: (text: string, final: boolean) => void, options: VoiceCaptureOptions) => {
      endRecording(false);
      const session = ++recordSessionRef.current;
      setError("");
      setListening(true);

      void navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      }).then((stream) => {
        if (session !== recordSessionRef.current) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        const type = preferredRecordingType();
        let recorder: MediaRecorder;
        try {
          recorder = type ? new MediaRecorder(stream, { mimeType: type }) : new MediaRecorder(stream);
        } catch (recorderError) {
          stream.getTracks().forEach((track) => track.stop());
          setListening(false);
          setError(microphoneErrorMessage(recorderError));
          return;
        }
        const chunks: Blob[] = [];
        recorder.ondataavailable = (event) => {
          if (event.data.size > 0) chunks.push(event.data);
        };

        let animationFrame: number | undefined;
        let audioContext: AudioContext | null = null;
        let finished = false;
        const maxTimer = window.setTimeout(() => finish(true), MAX_RECORDING_MS);
        // A phone can create the level meter suspended when recording did not
        // start from a tap (speaking practice starts after the coach speaks);
        // it then reads only silence and a pause would never be noticed.
        const resumeOnTouch = () => { void audioContext?.resume?.(); };
        document.addEventListener("pointerdown", resumeOnTouch);
        document.addEventListener("touchstart", resumeOnTouch);
        let lastCountdown: number | null = null;
        const reportCountdown = (seconds: number | null) => {
          if (seconds === lastCountdown) return;
          lastCountdown = seconds;
          options.onSilenceCountdown?.(seconds);
        };
        const cleanup = () => {
          document.removeEventListener("pointerdown", resumeOnTouch);
          document.removeEventListener("touchstart", resumeOnTouch);
          reportCountdown(null);
          window.clearTimeout(maxTimer);
          if (animationFrame !== undefined) window.cancelAnimationFrame(animationFrame);
          options.onAudioLevel?.(0);
          stream.getTracks().forEach((track) => track.stop());
          if (audioContext && audioContext.state !== "closed") void audioContext.close();
        };

        const deliverRecording = async () => {
          const audio = new Blob(chunks, { type: recorder.mimeType || type || "audio/webm" });
          if (!audio.size) {
            setError("No audio was recorded. Tap the microphone and try again.");
            onResult("", true);
            return;
          }
          setTranscribing(true);
          try {
            const text = (await transcribeRef.current?.(audio))?.trim() ?? "";
            if (session !== recordSessionRef.current) return;
            if (!text) setError("I couldn't hear any words in that recording. Tap the microphone and speak a little closer to the phone.");
            onResult(text, true);
          } catch (transcribeError) {
            if (session !== recordSessionRef.current) return;
            const reason = (transcribeError as Error)?.message || "the transcription service did not respond";
            setError(`Your answer couldn't be turned into text (${reason}). Tap the microphone to try again, or type your answer.`);
            onResult("", true);
          } finally {
            if (session === recordSessionRef.current) setTranscribing(false);
          }
        };

        function finish(deliver: boolean) {
          if (finished) return;
          finished = true;
          if (finishRecordingRef.current === finish) finishRecordingRef.current = null;
          const onStopped = () => {
            cleanup();
            if (session !== recordSessionRef.current) return;
            setListening(false);
            if (deliver) void deliverRecording();
          };
          if (recorder.state !== "inactive") {
            recorder.addEventListener("stop", onStopped, { once: true });
            recorder.stop();
          } else {
            onStopped();
          }
        }
        finishRecordingRef.current = finish;

        const AudioContextCtor = window.AudioContext
          || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
        if (AudioContextCtor) {
          try {
            audioContext = new AudioContextCtor();
            // A phone may create it suspended when this did not start from a tap.
            void audioContext.resume?.();
            const analyser = audioContext.createAnalyser();
            analyser.fftSize = 1024;
            audioContext.createMediaStreamSource(stream).connect(analyser);
            const samples = new Uint8Array(analyser.fftSize);
            const silenceMs = options.silenceMs ?? DEFAULT_SILENCE_MS;
            let speechDetected = false;
            let quietSince = 0;
            const measure = () => {
              if (finished) return;
              analyser.getByteTimeDomainData(samples);
              let sum = 0;
              for (const sample of samples) {
                const value = (sample - 128) / 128;
                sum += value * value;
              }
              const rms = Math.sqrt(sum / samples.length);
              options.onAudioLevel?.(Math.min(1, Math.max(0, (rms - 0.012) * 8.5)));
              const now = performance.now();
              if (rms >= 0.015) {
                speechDetected = true;
                quietSince = 0;
                reportCountdown(null);
                if (window.speechSynthesis?.speaking) window.speechSynthesis.cancel();
              } else if (speechDetected && options.autoStopOnSilence) {
                if (!quietSince) quietSince = now;
                const remaining = silenceMs - (now - quietSince);
                if (remaining <= 0) {
                  finish(true);
                  return;
                }
                reportCountdown(remaining <= 3000 ? Math.ceil(remaining / 1000) : null);
              }
              animationFrame = window.requestAnimationFrame(measure);
            };
            measure();
          } catch {
            // No level meter or auto-stop, but recording still works: the
            // student taps the microphone to finish.
          }
        }
        recorder.start(250);
      }).catch((microphoneError) => {
        if (session !== recordSessionRef.current) return;
        setListening(false);
        setError(microphoneErrorMessage(microphoneError));
      });
      return true;
    },
    [endRecording],
  );

  /** Starts listening. `onResult` is called with the running transcript
   * (accumulated final text + the current interim guess) on every update,
   * and once more with `final: true` when recognition ends. */
  const start = useCallback(
    (onResult: (text: string, final: boolean) => void, options: VoiceCaptureOptions = {}) => {
      setError("");
      if (recordingMode) return startRecording(onResult, options);
      const SpeechRecognitionAPI = getSpeechRecognitionAPI();
      if (!SpeechRecognitionAPI) {
        setError("Voice input isn't supported in this browser — try Chrome or Edge.");
        return false;
      }
      keepListeningRef.current = false;
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
      // Short utterances can remain interim when recording ends. Keep the
      // latest text so stopping does not clear a usable one-word result.
      let latestText = "";
      let completedSessionsText = "";
      const resultSlots = new Map<number, SpeechResultSnapshot>();
      recognition.onresult = (event) => {
        const assembled = updateSpeechResultSlots(resultSlots, event);
        finalText = assembled.finalText;
        latestText = assembled.displayText;
        const runningText = joinSpeechSegments([completedSessionsText, latestText]);
        // Raw Web Speech result diagnostics are opt-in because transcripts
        // may contain personal information. Enable on a test device with:
        // localStorage.setItem("digidara_speech_debug", "1")
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
      };
      recognition.onerror = (event) => {
        if (recognitionRef.current !== recognition) return;
        // Browsers commonly emit no-speech before ending a recognition
        // session. onend restarts that session while the question timer runs.
        if (event.error === "no-speech") return;
        keepListeningRef.current = false;
        setListening(false);
        setError(ERROR_MESSAGES[event.error] || "Speech recognition stopped unexpectedly.");
      };
      recognition.onstart = () => {
        setListening(true);
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
        if (speechDebugEnabled()) console.debug("[DigiDARA speech end]", {
          completedText: completedSessionsText,
          restarting: keepListeningRef.current,
        });

        if (keepListeningRef.current) {
          window.setTimeout(() => {
            if (!keepListeningRef.current || recognitionRef.current !== recognition) return;
            try {
              recognition.start();
            } catch {
              keepListeningRef.current = false;
              recognitionRef.current = null;
              setListening(false);
              setError("Speech recognition stopped unexpectedly. Restart the microphone or type your answer.");
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
              if (now - quietSince >= (options.silenceMs ?? DEFAULT_SILENCE_MS)) {
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
    [locale, recordingMode, startRecording],
  );

  return {
    supported: recordingMode || Boolean(getSpeechRecognitionAPI()),
    /** True on a phone with a server transcriber: text arrives once, after recording stops. */
    recordingMode,
    listening,
    transcribing,
    error,
    start,
    stop,
  };
}
