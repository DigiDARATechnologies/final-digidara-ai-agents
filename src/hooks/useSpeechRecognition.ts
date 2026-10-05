import { useCallback, useEffect, useRef, useState } from "react";
import {
  joinSpeechSegments,
  removeMobileTranscriptLoops,
  updateSpeechResultSlots,
  type SpeechResultSnapshot,
} from "../lib/speechTranscript";
import {
  audioRecordingSupported,
  isMobileVoiceDevice,
  microphoneErrorMessage,
  preferredRecordingType,
} from "../lib/voiceCapture";

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
  /** How long a pause (after some speech) ends the recording. Default 7s. */
  silenceMs?: number;
  /** Recording mode: whole seconds left before a pause ends the recording
   * (only in its last 3 seconds), or null once speech resumes. */
  onSilenceCountdown?: (seconds: number | null) => void;
  /** Recording mode: the student was heard (by the level meter, or new words
   * in a live preview when the meter is not measuring). Arrives before any
   * transcript, so "has the student spoken yet?" never waits for text. */
  onVoiceDetected?: () => void;
};

/** Sends a recorded answer to the server and resolves with its transcript. */
export type AudioTranscriber = (audio: Blob) => Promise<string>;

/** Longest single recording on a phone, so an uploaded answer stays small. */
const MAX_RECORDING_MS = 3 * 60 * 1000;
/** Recording mode live text: how often the answer so far is re-transcribed,
 * and at most how many times per recording (about two minutes of speech). */
const PREVIEW_INTERVAL_MS = 3_000;
const MAX_PREVIEWS = 40;
const DEFAULT_SILENCE_MS = 7000;

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

/** Speech-to-text for the chat composer: dictate into the text input
 * instead of typing. The recognized text is sent through the exact same
 * `onSend(text)` path as anything typed.
 *
 * Two ways of getting there:
 * - Desktop (and any agent without a `transcribe` function): the browser's
 *   live Web Speech recognition, words appearing as they are spoken.
 * - Phones, when `transcribe` is given: record the answer on a single
 *   microphone stream and have the server transcribe it when recording
 *   stops. Live recognition is unreliable on phones -- see voiceCapture.ts.
 *   With `preview` as well, the recording so far is re-transcribed about
 *   every 3 seconds and reported (not final) so the text appears as the
 *   student speaks; the text reported as final is still `transcribe`'s.
 * - `alwaysRecord` (with `transcribe`): use the record-then-transcribe path on
 *   every device, not just phones -- the general chat sends all voice to the
 *   server's OpenAI transcription, which also works in browsers that have no
 *   live speech recognition (Firefox, Safari on desktop). */
export default function useSpeechRecognition(locale = "en-US", transcribe?: AudioTranscriber, preview?: AudioTranscriber, alwaysRecord = false) {
  const [listening, setListening] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [error, setError] = useState("");
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const keepListeningRef = useRef(false);
  const vadCleanupRef = useRef<(() => void) | null>(null);
  const retryCountRef = useRef(0);
  const transcribeRef = useRef(transcribe);
  transcribeRef.current = transcribe;
  const previewRef = useRef(preview);
  previewRef.current = preview;
  const recordingMode = Boolean(transcribe) && (alwaysRecord || isMobileVoiceDevice()) && audioRecordingSupported();
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

  const cancel = useCallback(() => {
    // Also cancels a recording whose microphone is still opening.
    if (recordingMode || finishRecordingRef.current) {
      endRecording(false);
      return;
    }
    stop();
  }, [endRecording, recordingMode, stop]);

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
        // Shared by the level meter and the live preview below.
        let speechDetected = false;
        let quietSince = 0;
        const meterRunning = () => audioContext?.state === "running";
        let previewTimer: number | undefined;
        let lastCountdown: number | null = null;
        const reportCountdown = (seconds: number | null) => {
          if (seconds === lastCountdown) return;
          lastCountdown = seconds;
          options.onSilenceCountdown?.(seconds);
        };
        const cleanup = () => {
          window.clearInterval(previewTimer);
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
            const rawText = (await transcribeRef.current?.(audio))?.trim() ?? "";
            const text = removeMobileTranscriptLoops(rawText);
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
                options.onVoiceDetected?.();
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

        // Live text: re-transcribe the recording so far while the student is
        // speaking. When the meter is not measuring (a phone can keep it
        // suspended), do not wait for it to hear speech, and let new words in
        // a preview stand in for it so a pause is still noticed.
        const previewTranscribe = previewRef.current;
        if (previewTranscribe) {
          let lastPreviewAt = 0;
          let previewChunks = 0;
          let previewCount = 0;
          let inFlight = false;
          let lastText = "";
          previewTimer = window.setInterval(() => {
            if (finished || inFlight || previewCount >= MAX_PREVIEWS) return;
            if (!speechDetected && meterRunning()) return;
            if (Date.now() - lastPreviewAt < PREVIEW_INTERVAL_MS || chunks.length <= previewChunks) return;
            inFlight = true;
            previewCount += 1;
            previewChunks = chunks.length;
            lastPreviewAt = Date.now();
            const audio = new Blob(chunks, { type: recorder.mimeType || type || "audio/webm" });
            previewTranscribe(audio)
              .then((text) => {
                if (finished || session !== recordSessionRef.current) return;
                const trimmed = removeMobileTranscriptLoops(text);
                if (!trimmed || trimmed === lastText) return;
                lastText = trimmed;
                if (!meterRunning()) {
                  speechDetected = true;
                  quietSince = performance.now();
                  options.onVoiceDetected?.();
                }
                onResult(trimmed, false);
              })
              .catch(() => {
                // A missed preview only delays the live text; the whole
                // recording is still transcribed when it stops.
              })
              .finally(() => { inFlight = false; });
          }, 250);
        }
      }).catch((microphoneError) => {
        if (session !== recordSessionRef.current) return;
        setListening(false);
        setError(microphoneErrorMessage(microphoneError));
      });
      return true;
    },
    [endRecording],
  );

  /** Starts listening. onResult is called with the running transcript
   * (accumulated final text + the current interim guess) on every update,
   * and once more with final: true when recognition ends. */
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
        const unfilteredRunningText = joinSpeechSegments([completedSessionsText, latestText]);
        const runningText = isMobileDevice
          ? removeMobileTranscriptLoops(unfilteredRunningText)
          : unfilteredRunningText;
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
        const completedText = completedSessionsText.trim();
        onResult(isMobileDevice ? removeMobileTranscriptLoops(completedText) : completedText, true);
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
              // Silence allowance before VAD stops, coordinating with auto-submit:
              if (now - quietSince >= (options.silenceMs ?? 12000)) {
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
    /** Ends listening without using what was heard. In recording mode the
     * recording is thrown away (not transcribed); otherwise it is stop(). */
    cancel,
  };
}
