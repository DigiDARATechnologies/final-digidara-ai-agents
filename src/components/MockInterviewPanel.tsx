import { useEffect, useRef, useState } from "react";
import useSpeechRecognition from "../hooks/useSpeechRecognition";
import { isMobileVoiceDevice, microphoneErrorMessage } from "../lib/voiceCapture";
import { downloadMockInterviewReport, transcribeMockInterviewAudio, transcribeMockInterviewPreview } from "../lib/mockInterviewApi";
import { AFTER_PROMPT_END_MS, AWAY_PROMPT, secondsUntilAction, silenceAction } from "../lib/answerSilence";
import { speakNatural as speakBrowserText } from "../lib/voiceEngine";
import type { MockInterviewAnswerTiming, MockInterviewFlowState } from "../lib/mockInterviewFlow";

const TIME_LIMIT_SECONDS = { beginner: 60, intermediate: 90, advanced: 120 } as const;

/** Microphone level above which the candidate counts as speaking, and for how
 * many consecutive 100ms samples -- a single click or tap is not speech. */
const VOICE_LEVEL = 0.015;
const VOICE_SAMPLES = 2;
/** Phone live preview: how often the answer so far is re-transcribed, and at
 * most how many times per answer (about two minutes of speech). */
const PREVIEW_INTERVAL_MS = 3_000;
const MAX_PREVIEWS = 40;

interface Props {
  state: MockInterviewFlowState;
  busy: boolean;
  onAnswer: (answer: string, timing: MockInterviewAnswerTiming) => void;
  /** "inactive": ended automatically because the candidate never answered. */
  onExit: (reason?: "inactive") => void;
  onPracticeWeakTopics?: (subjects: string[]) => void;
}

function score(value: number | null | undefined): string {
  return value == null ? "-" : `${value}/10`;
}

function feedbackPoints(value?: string): string[] {
  if (!value) return [];
  try {
    const parsed: unknown = JSON.parse(value);
    if (Array.isArray(parsed)) return parsed.map(String).filter(Boolean);
  } catch { /* Older reports contain plain text. */ }
  return value.split(/\r?\n/).map((line) => line.replace(/^\s*[-*\d.)]+\s*/, "").trim()).filter(Boolean);
}

function compactFeedback(value?: string): string {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (!text) return "";
  const sentences = text.split(/(?<=[.!?])\s+/).slice(0, 2).join(" ");
  if (sentences.length <= 280) return sentences;
  return `${sentences.slice(0, 277).trimEnd()}...`;
}

function isQuestionEcho(answer: string, question?: string): boolean {
  const normalize = (value: string) => value.toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, "");
  const normalizedAnswer = normalize(answer);
  return Boolean(normalizedAnswer && question && normalizedAnswer === normalize(question));
}

export default function MockInterviewPanel({ state, busy, onAnswer, onExit, onPracticeWeakTopics }: Props) {
  const speech = useSpeechRecognition();
  const [spokenAnswer, setSpokenAnswer] = useState("");
  const [typedAnswer, setTypedAnswer] = useState("");
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const [timerEpoch, setTimerEpoch] = useState(0);
  const [voiceStatus, setVoiceStatus] = useState("");
  const [downloadError, setDownloadError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [recording, setRecording] = useState(false);
  const [hasCapturedAudio, setHasCapturedAudio] = useState(false);
  const submittedRef = useRef(false);
  const timerIntervalRef = useRef<number | null>(null);
  const spokenRef = useRef("");
  const typedRef = useRef("");
  const typedEditedRef = useRef(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const capturedAudioRef = useRef<Blob | null>(null);
  const deadlineRef = useRef<number | null>(null);
  const startedAtRef = useRef<number | null>(null);
  const onAnswerRef = useRef(onAnswer);
  onAnswerRef.current = onAnswer;
  const beginAnswerRef = useRef<() => void>(() => {});
  const stopSpeechRef = useRef(speech.stop);
  stopSpeechRef.current = speech.stop;
  const onExitRef = useRef(onExit);
  onExitRef.current = onExit;
  // Silence handling (see lib/answerSilence.ts).
  const answeringSinceRef = useRef(0);
  const lastVoiceAtRef = useRef<number | null>(null);
  const promptedAtRef = useRef<number | null>(null);
  const micPausedRef = useRef(false);
  // A microphone is actually on (recording, or the browser recognizer). With
  // none, the candidate can only type, so nothing happens automatically.
  const micActiveRef = useRef(false);
  const vadStopRef = useRef<(() => void) | null>(null);
  // The volume meter is actually measuring. A phone can create it suspended
  // (not started from a tap), and then it only ever reads silence.
  const vadWorkingRef = useRef(false);
  // The interviewer's own voice is playing ("Hey, are you there?"). Tracked
  // here rather than read from speechSynthesis.speaking, which Android Chrome
  // can leave stuck at true -- that silenced the meter for the whole answer.
  const ttsActiveRef = useRef(false);
  const lastPreviewTextRef = useRef("");
  const previewFailuresRef = useRef(0);
  const [awayPrompt, setAwayPrompt] = useState(false);
  const [silenceHint, setSilenceHint] = useState("");
  // Phone live preview.
  const previewSessionRef = useRef(0);
  const previewInFlightRef = useRef(false);
  const previewCountRef = useRef(0);
  const previewChunksRef = useRef(0);
  const lastPreviewAtRef = useRef(0);
  const submitAnswerRef = useRef<(answer: string, timedOut?: boolean) => Promise<void>>(async () => {});

  const isLive = state.step === "in_interview" && Boolean(state.question && state.interviewId && state.questionOrder);
  const questionKey = isLive ? `${state.interviewId}:${state.questionOrder}` : "";
  const timeLimit = TIME_LIMIT_SECONDS[state.difficulty ?? "intermediate"];
  const recordingSupported = typeof window !== "undefined"
    && "MediaRecorder" in window
    && Boolean(navigator.mediaDevices?.getUserMedia);
  const mobileVoice = isMobileVoiceDevice();
  // Why the recorder could not start, shown instead of a bare "unavailable".
  const micErrorRef = useRef("");

  /** Starts the browser's live transcript next to the recording -- except on
   * a phone that is already recording: there the two compete for the
   * microphone and the recording (transcribed by OpenAI at submit) is the
   * reliable one. */
  function startLiveTranscript(recordingStarted: boolean, onText: (text: string) => void = acceptVoiceTranscript): boolean {
    if (!speech.supported || (mobileVoice && recordingStarted)) return false;
    return speech.start(onText);
  }

  function microphoneStatus(recordingStarted: boolean, startedListening: boolean, retry = false): string {
    micActiveRef.current = recordingStarted || startedListening;
    if (recordingStarted) {
      if (startedListening) return retry ? "No answer detected. Listening again - please answer the question." : "Listening - microphone is on";
      if (mobileVoice) return `${retry ? "No answer detected. " : ""}Recording your answer - press Submit when you finish and it will be turned into text.`;
      return retry ? "No answer detected. Recording again for OpenAI transcription." : "Recording - OpenAI will transcribe when you submit";
    }
    if (startedListening) return retry ? "No answer detected. Listening again - please answer the question." : "Listening with browser transcription";
    return micErrorRef.current
      ? `${micErrorRef.current} You can also type your answer below.`
      : retry ? "No answer detected. Please type your answer." : "Microphone is unavailable. Type your answer below.";
  }

  /** The candidate was heard: the silence rules now wait for a pause. */
  function markVoice() {
    lastVoiceAtRef.current = Date.now();
    if (promptedAtRef.current !== null) {
      promptedAtRef.current = null;
      setAwayPrompt(false);
    }
  }

  function resetSilenceTracking() {
    answeringSinceRef.current = Date.now();
    lastVoiceAtRef.current = null;
    promptedAtRef.current = null;
    micPausedRef.current = false;
    micActiveRef.current = false;
    previewSessionRef.current += 1;
    previewInFlightRef.current = false;
    previewCountRef.current = 0;
    previewChunksRef.current = 0;
    lastPreviewAtRef.current = 0;
    lastPreviewTextRef.current = "";
    previewFailuresRef.current = 0;
    setAwayPrompt(false);
    setSilenceHint("");
  }

  /** `fromPreview`: text from the phone's live preview transcription, which
   * lags behind the voice and so is not itself a sign of speaking. */
  function acceptVoiceTranscript(text: string, fromPreview = false) {
    if (!text || submittedRef.current) return;
    if (isQuestionEcho(text, state.question) || isQuestionEcho(text, AWAY_PROMPT)) return;
    // The browser recognizer can pick up the interviewer's own voice.
    if (!fromPreview && ttsActiveRef.current) return;
    if (!fromPreview) markVoice();
    spokenRef.current = text;
    setSpokenAnswer(text);
    if (!typedEditedRef.current) {
      typedRef.current = text;
      setTypedAnswer(text);
    }
  }

  /** Listens to the recording's own microphone stream for speech, so the
   * silence rules work on phones, where no browser recognizer runs. */
  function startVoiceDetection(stream: MediaStream) {
    vadStopRef.current?.();
    const AudioContextCtor = window.AudioContext
      || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextCtor) return;
    let context: AudioContext;
    try {
      context = new AudioContextCtor();
      const audioContext = context;
      const updateWorking = () => { vadWorkingRef.current = audioContext.state === "running"; };
      // Started without a tap, a phone may keep it suspended until the next
      // one: resume on the first touch, and until then the live preview does
      // not wait for the meter to hear speech.
      const resumeOnTouch = () => { void audioContext.resume?.().then(updateWorking, updateWorking); };
      document.addEventListener("pointerdown", resumeOnTouch);
      document.addEventListener("touchstart", resumeOnTouch);
      audioContext.onstatechange = updateWorking;
      updateWorking();
      void audioContext.resume?.().then(updateWorking, updateWorking);
      const analyser = context.createAnalyser();
      analyser.fftSize = 1024;
      context.createMediaStreamSource(stream).connect(analyser);
      const samples = new Uint8Array(analyser.fftSize);
      let loud = 0;
      const timer = window.setInterval(() => {
        if (micPausedRef.current || ttsActiveRef.current) {
          loud = 0;
          return;
        }
        analyser.getByteTimeDomainData(samples);
        let sum = 0;
        for (const sample of samples) {
          const value = (sample - 128) / 128;
          sum += value * value;
        }
        loud = Math.sqrt(sum / samples.length) >= VOICE_LEVEL ? loud + 1 : 0;
        if (loud >= VOICE_SAMPLES) markVoice();
      }, 100);
      vadStopRef.current = () => {
        window.clearInterval(timer);
        document.removeEventListener("pointerdown", resumeOnTouch);
        document.removeEventListener("touchstart", resumeOnTouch);
        vadWorkingRef.current = false;
        if (context.state !== "closed") void context.close();
        vadStopRef.current = null;
      };
    } catch {
      // No level meter: the browser recognizer's text (desktop) still counts
      // as speech, and the question timer still applies.
    }
  }

  function closeAudioStream() {
    vadStopRef.current?.();
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;
  }

  async function beginAudioCapture(): Promise<boolean> {
    if (!recordingSupported) return false;
    // Mobile Web Speech may end after a pause even while MediaRecorder is
    // correctly capturing the full answer. Restart only recognition in that
    // case; resetting this recorder would discard the answer's first part.
    if (mediaRecorderRef.current?.state === "recording") return true;
    if (mediaRecorderRef.current?.state === "paused") {
      mediaRecorderRef.current.resume();
      setRecording(true);
      return true;
    }
    closeAudioStream();
    audioChunksRef.current = [];
    capturedAudioRef.current = null;
    setHasCapturedAudio(false);
    micErrorRef.current = "";
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      const appleMobile = /iPhone|iPad|iPod/i.test(navigator.userAgent);
      const candidateTypes = appleMobile
        ? ["audio/mp4", "audio/mp4;codecs=mp4a.40.2", "audio/webm;codecs=opus", "audio/webm"]
        : ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4", "audio/mp4;codecs=mp4a.40.2"];
      const preferredType = typeof MediaRecorder.isTypeSupported === "function"
        ? candidateTypes.find((type) => MediaRecorder.isTypeSupported(type))
        : undefined;
      const recorder = preferredType ? new MediaRecorder(stream, { mimeType: preferredType }) : new MediaRecorder(stream);
      mediaStreamRef.current = stream;
      mediaRecorderRef.current = recorder;
      startVoiceDetection(stream);
      recorder.addEventListener("dataavailable", (event) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data);
      });
      await new Promise<void>((resolve, reject) => {
        recorder.addEventListener("start", () => resolve(), { once: true });
        recorder.addEventListener("error", () => reject(new Error("Audio recording could not start.")), { once: true });
        recorder.start(250);
      });
      setRecording(true);
      return true;
    } catch (error) {
      micErrorRef.current = microphoneErrorMessage(error);
      mediaRecorderRef.current = null;
      setRecording(false);
      closeAudioStream();
      return false;
    }
  }

  async function finishAudioCapture(): Promise<Blob | null> {
    const recorder = mediaRecorderRef.current;
    if (!recorder) {
      closeAudioStream();
      return capturedAudioRef.current;
    }
    if (recorder.state !== "inactive") {
      await new Promise<void>((resolve) => {
        recorder.addEventListener("stop", () => resolve(), { once: true });
        recorder.stop();
      });
    }
    const type = recorder.mimeType || audioChunksRef.current[0]?.type || "audio/webm";
    const blob = audioChunksRef.current.length ? new Blob(audioChunksRef.current, { type }) : null;
    mediaRecorderRef.current = null;
    closeAudioStream();
    setRecording(false);
    if (blob?.size) {
      capturedAudioRef.current = blob;
      setHasCapturedAudio(true);
    }
    return blob;
  }

  function discardAudioCapture() {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") recorder.stop();
    mediaRecorderRef.current = null;
    audioChunksRef.current = [];
    capturedAudioRef.current = null;
    setRecording(false);
    setHasCapturedAudio(false);
    closeAudioStream();
  }

  useEffect(() => {
    if (!questionKey) return;
    let active = true;
    let started = false;
    submittedRef.current = false;
    spokenRef.current = "";
    typedRef.current = "";
    typedEditedRef.current = false;
    capturedAudioRef.current = null;
    setHasCapturedAudio(false);
    setSpokenAnswer("");
    setTypedAnswer("");
    const storageKey = `digidara_mock_interview_deadline_${questionKey}`;
    const existingDeadline = Number(sessionStorage.getItem(storageKey));

    async function startAnswering() {
      if (!active || submittedRef.current || started) return;
      started = true;
      let deadline = existingDeadline;
      if (!deadline || !Number.isFinite(deadline)) {
        deadline = Date.now() + timeLimit * 1000;
        sessionStorage.setItem(storageKey, String(deadline));
      }
      deadlineRef.current = deadline;
      startedAtRef.current = deadline - timeLimit * 1000;
      setSecondsLeft(Math.max(0, Math.ceil((deadline - Date.now()) / 1000)));
      resetSilenceTracking();
      setVoiceStatus(recordingSupported || speech.supported ? "Starting microphone..." : "Type your answer below");
      if (deadline > Date.now()) {
        const recordingStarted = await beginAudioCapture();
        if (!active || submittedRef.current) {
          discardAudioCapture();
          return;
        }
        const startedListening = startLiveTranscript(recordingStarted, (text) => {
          if (active) acceptVoiceTranscript(text);
        });
        setVoiceStatus(microphoneStatus(recordingStarted, startedListening));
      }
    }
    beginAnswerRef.current = () => { void startAnswering(); };

    if (existingDeadline && Number.isFinite(existingDeadline)) {
      startAnswering();
    } else if ("speechSynthesis" in window && "SpeechSynthesisUtterance" in window) {
      setVoiceStatus("Reading the question aloud");
      // The difficulty/Start action unlocks speech before this async panel is
      // mounted. Wait for browser voices and fall back to listening if the
      // browser still rejects TTS, so the interview cannot get stuck.
      void speakBrowserText(state.question ?? "", {
        onEnd: startAnswering,
        onError: () => startAnswering(),
      }).then((started) => {
        if (!started) startAnswering();
      });
    } else {
      startAnswering();
    }

    return () => {
      active = false;
      beginAnswerRef.current = () => {};
      stopSpeechRef.current();
      discardAudioCapture();
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    };
    // A new question, rather than a parent rerender, starts a new voice session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [questionKey]);

  async function submitAnswer(answer: string, timedOut = false) {
    if (!isLive || busy || transcribing || submittedRef.current) return;
    const initialAnswer = answer.trim();
    if (!typedEditedRef.current && isQuestionEcho(initialAnswer, state.question)) {
      spokenRef.current = "";
      typedRef.current = "";
      setSpokenAnswer("");
      setTypedAnswer("");
      setVoiceStatus("That was the interview question, not an answer. Please speak or type your answer.");
      return;
    }
    const hasAudio = recording
      || hasCapturedAudio
      || Boolean(mediaRecorderRef.current)
      || Boolean(capturedAudioRef.current?.size);
    if (!initialAnswer && !timedOut && !hasAudio) {
      setVoiceStatus("Speak or type an answer before submitting.");
      return;
    }
    submittedRef.current = true;
    if (timerIntervalRef.current !== null) {
      window.clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
    speech.stop();
    const shouldImproveTranscript = !typedEditedRef.current
      && hasAudio
      && Boolean(state.sessionToken && state.interviewId && state.questionOrder);
    if (shouldImproveTranscript) {
      setTranscribing(true);
      setVoiceStatus("Transcribing your recording with OpenAI...");
    }
    const recordedAudio = await finishAudioCapture();
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    const elapsed = startedAtRef.current ? Math.round((Date.now() - startedAtRef.current) / 1000) : 0;
    let finalAnswer = initialAnswer;
    if (shouldImproveTranscript && recordedAudio?.size && state.sessionToken && state.interviewId && state.questionOrder) {
      try {
        const result = await transcribeMockInterviewAudio(state.sessionToken, state.interviewId, state.questionOrder, recordedAudio);
        if (result.transcript?.trim()) {
          finalAnswer = isQuestionEcho(result.transcript.trim(), state.question) ? "" : result.transcript.trim();
          spokenRef.current = finalAnswer;
          typedRef.current = finalAnswer;
          setSpokenAnswer(finalAnswer);
          setTypedAnswer(finalAnswer);
        }
      } catch {
        setVoiceStatus(initialAnswer
          ? "OpenAI transcription was unavailable. Using the live transcript."
          : "OpenAI could not transcribe this recording. Please start the microphone and try again.");
      } finally {
        setTranscribing(false);
      }
    } else if (shouldImproveTranscript) {
      setVoiceStatus("Using the live transcript because no complete audio recording was available.");
      setTranscribing(false);
    }
    if (!finalAnswer && !timedOut) {
      // Empty room audio can be hallucinated as the prompt question because
      // the transcription request includes that question for technical-term
      // context. Do not grade the prompt as the candidate's response.
      submittedRef.current = false;
      setTimerEpoch((epoch) => epoch + 1);
      resetSilenceTracking();
      const recordingStarted = recordingSupported ? await beginAudioCapture() : false;
      const startedListening = startLiveTranscript(recordingStarted);
      setVoiceStatus(microphoneStatus(recordingStarted, startedListening, true));
      return;
    }
    sessionStorage.removeItem(`digidara_mock_interview_deadline_${questionKey}`);
    onAnswerRef.current(finalAnswer, { timeTakenSec: Math.max(0, Math.min(timeLimit, elapsed)), timedOut: timedOut && !finalAnswer });
  }

  submitAnswerRef.current = submitAnswer;

  /** Phone only: re-transcribe the answer so far so it appears in the box
   * while the candidate is still speaking. */
  function refreshLivePreview() {
    const recorder = mediaRecorderRef.current;
    const chunks = audioChunksRef.current;
    if (!state.sessionToken || !state.interviewId || !state.questionOrder) return;
    if (!recorder || recorder.state !== "recording" || previewInFlightRef.current) return;
    if (previewCountRef.current >= MAX_PREVIEWS || chunks.length <= previewChunksRef.current) return;
    previewInFlightRef.current = true;
    previewCountRef.current += 1;
    previewChunksRef.current = chunks.length;
    lastPreviewAtRef.current = Date.now();
    const session = previewSessionRef.current;
    const audio = new Blob(chunks, { type: recorder.mimeType || chunks[0]?.type || "audio/webm" });
    transcribeMockInterviewPreview(state.sessionToken, state.interviewId, state.questionOrder, audio)
      .then((result) => {
        if (session !== previewSessionRef.current || submittedRef.current) return;
        if (previewFailuresRef.current >= 2) setVoiceStatus(microphoneStatus(true, false));
        previewFailuresRef.current = 0;
        const text = result.transcript?.trim() ?? "";
        if (!text || isQuestionEcho(text, state.question) || isQuestionEcho(text, AWAY_PROMPT)) return;
        // New words are proof of speech even when the volume meter hears
        // nothing, so the silence rules keep working without it.
        if (text !== lastPreviewTextRef.current) {
          lastPreviewTextRef.current = text;
          markVoice();
        }
        acceptVoiceTranscript(text, true);
      })
      .catch((error) => {
        // One missed preview only delays the live text; the full recording is
        // still transcribed on submit. Repeated failures are shown.
        if (session !== previewSessionRef.current || submittedRef.current) return;
        previewFailuresRef.current += 1;
        if (previewFailuresRef.current === 2) {
          const reason = error instanceof Error && error.message ? ` (${error.message})` : "";
          setVoiceStatus(`Live text isn't available right now${reason}. Keep speaking - your whole answer is still turned into text when you submit.`);
        }
      })
      .finally(() => {
        if (session === previewSessionRef.current) previewInFlightRef.current = false;
      });
  }

  function askAreYouThere() {
    promptedAtRef.current = Date.now();
    setAwayPrompt(true);
    if ("speechSynthesis" in window && "SpeechSynthesisUtterance" in window) {
      ttsActiveRef.current = true;
      const done = () => { ttsActiveRef.current = false; };
      // A safety net in case the browser never reports the end.
      window.setTimeout(done, 4_000);
      void speakBrowserText(AWAY_PROMPT, { onEnd: done, onError: done }).then((started) => { if (!started) done(); });
    }
  }

  function endForInactivity() {
    submittedRef.current = true;
    if (timerIntervalRef.current !== null) {
      window.clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
    speech.stop();
    discardAudioCapture();
    sessionStorage.removeItem(`digidara_mock_interview_deadline_${questionKey}`);
    setAwayPrompt(false);
    setVoiceStatus("No answer was heard, so the interview has ended.");
    onExitRef.current("inactive");
  }

  useEffect(() => {
    if (!isLive || secondsLeft === null || submittedRef.current || busy || transcribing) return;
    const check = () => {
      if (submittedRef.current) return;
      const snapshot = {
        now: Date.now(),
        answeringSince: answeringSinceRef.current,
        lastVoiceAt: lastVoiceAtRef.current,
        promptedAt: promptedAtRef.current,
        manual: !micActiveRef.current || micPausedRef.current || typedEditedRef.current,
      };
      const next = secondsUntilAction(snapshot);
      setSilenceHint(!next ? ""
        : next.action === "submit" ? `Pause detected - submitting your answer in ${next.seconds}s. Keep talking to continue.`
          : `No answer yet - the interview ends in ${next.seconds}s unless you start speaking.`);
      const action = silenceAction(snapshot);
      if (action === "submit") void submitAnswerRef.current(typedRef.current || spokenRef.current);
      else if (action === "prompt") askAreYouThere();
      else if (action === "end") endForInactivity();
      // Live text on a phone. Wait for the meter to hear speech only when the
      // meter is known to work; otherwise every new stretch of audio is sent.
      else if (mobileVoice && !speech.listening
        && (lastVoiceAtRef.current !== null || !vadWorkingRef.current)
        && snapshot.now - lastPreviewAtRef.current >= PREVIEW_INTERVAL_MS) refreshLivePreview();
    };
    const timer = window.setInterval(check, 250);
    return () => window.clearInterval(timer);
    // Refs carry the live values; restart only when the answer window changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [questionKey, secondsLeft !== null, busy, transcribing, timerEpoch]);

  useEffect(() => {
    if (!isLive || secondsLeft === null || submittedRef.current) return;
    const updateTimer = () => {
      if (submittedRef.current) return;
      const remaining = Math.max(0, Math.ceil(((deadlineRef.current ?? Date.now()) - Date.now()) / 1000));
      setSecondsLeft(remaining);
      if (remaining === 0) void submitAnswer(typedRef.current || spokenRef.current, true);
    };
    const timer = window.setInterval(updateTimer, 250);
    timerIntervalRef.current = timer;
    const onVisibilityChange = () => { if (!document.hidden) updateTimer(); };
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      window.clearInterval(timer);
      if (timerIntervalRef.current === timer) timerIntervalRef.current = null;
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
    // The deadline is stable for the mounted question.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [questionKey, secondsLeft !== null, busy, timerEpoch]);

  async function downloadReport() {
    if (!state.sessionToken || !state.interviewId || downloading) return;
    setDownloadError("");
    setDownloading(true);
    try {
      await downloadMockInterviewReport(state.sessionToken, state.interviewId);
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : "The PDF could not be downloaded.");
    } finally {
      setDownloading(false);
    }
  }

  if (state.step === "completed" && state.summary) {
    const summary = state.summary;
    const metrics = [
      ["Overall score", summary.overall_score],
      ["Knowledge score", summary.technical_accuracy],
      ["Communication score", summary.communication_clarity],
      ["Confidence score", summary.confidence],
    ] as const;
    return <section className="mock-interview-panel mock-interview-report" aria-label="Mock interview report">
      <div className="mock-interview-header"><div><small>INTERVIEW COMPLETE</small><h3>Your interview report</h3></div></div>
      <div className="mock-interview-scores">{metrics.map(([label, value]) => <div key={label} className="mock-interview-score"><span>{label}</span><strong>{score(value)}</strong></div>)}</div>
      {summary.max_marks != null && <p className="mock-interview-scorecard-total">Correct-answer score: {summary.total_marks ?? 0} / {summary.max_marks} ({summary.max_marks} questions)</p>}
      {summary.feedback && <p className="mock-interview-report-feedback">{compactFeedback(summary.feedback)}</p>}
      {(summary.strengths || summary.weaknesses) && <div className="mock-interview-feedback-grid">
        <div className="mock-interview-strengths"><strong>Strengths</strong>{feedbackPoints(summary.strengths).map((point, index) => <p key={index}>{point}</p>)}</div>
        <div className="mock-interview-weaknesses"><strong>Areas to Improve</strong>{feedbackPoints(summary.weaknesses).map((point, index) => <p key={index}>{point}</p>)}</div>
      </div>}
      <div className="mock-interview-report-actions">
        {Boolean(summary.subject_breakdown?.weak_subjects?.length) && onPracticeWeakTopics && <button type="button" className="btn btn-outline mock-interview-weak-topic-action" onClick={() => onPracticeWeakTopics(summary.subject_breakdown?.weak_subjects || [])} disabled={busy}>Practice Weak Skills</button>}
        <button type="button" className="btn btn-primary" onClick={downloadReport} disabled={downloading}>{downloading ? "Preparing PDF..." : "Download PDF report"}</button>
      </div>
      {downloadError && <p className="mock-interview-error" role="alert">{downloadError}</p>}
    </section>;
  }

  if (!isLive) return null;
  const activeAnswer = typedAnswer.trim() || spokenAnswer.trim();
  const canSubmit = Boolean(activeAnswer) || recording || hasCapturedAudio || Boolean(mediaRecorderRef.current);
  const currentQuestion = state.realQuestionIndex ?? state.questionOrder ?? 1;
  const totalQuestions = state.totalQuestions ?? 10;
  const progressPercent = Math.min(100, Math.max(0, (currentQuestion / totalQuestions) * 100));
  return <section className="mock-interview-panel" aria-label="Live mock interview">
    <div className="mock-interview-header"><div><small>LIVE INTERVIEW</small><p className="mock-interview-round">{state.roundType === "hr" ? "HR interview" : state.roleName || state.subject} Â· {state.difficulty}</p></div>
      <div className="mock-interview-progress" aria-label={`Question ${currentQuestion} of ${totalQuestions}`}><span>{currentQuestion}/{totalQuestions}</span><div className="mock-interview-progress-track"><i style={{ width: `${progressPercent}%` }} /></div></div>
      <div className={`mock-interview-timer${secondsLeft !== null && secondsLeft <= 15 ? " warning" : ""}`} role="timer"><span>Time left</span><strong>{secondsLeft === null ? "-" : `${String(Math.floor(secondsLeft / 60)).padStart(2, "0")}:${String(secondsLeft % 60).padStart(2, "0")}`}</strong></div>
    </div>
    <div className="mock-interview-question"><span className="mock-interview-question-number" aria-hidden="true">{currentQuestion}.</span><span>{state.question}</span></div>
    <div className={`mock-interview-voice${speech.listening || recording ? " listening" : ""}`}>
      <span className="mock-interview-voice-status" aria-live="polite"><i aria-hidden="true" />{voiceStatus}{speech.listening ? " Â· Microphone on" : ""}</span>
      <div>
        {secondsLeft === null && <button type="button" className="btn btn-outline" onClick={() => { if ("speechSynthesis" in window) window.speechSynthesis.cancel(); beginAnswerRef.current(); }}>Start answering now</button>}
        {(speech.supported || recordingSupported) && <button type="button" className="btn btn-outline" disabled={busy || transcribing || secondsLeft === null} onClick={() => {
          if (recording || speech.listening) {
            micPausedRef.current = true;
            speech.stop();
            if (mediaRecorderRef.current?.state === "recording") {
              mediaRecorderRef.current.pause();
              setRecording(false);
            }
            setVoiceStatus("Microphone paused - restart it or type below.");
          }
          else {
            // Resuming: the silence rules start again from now.
            micPausedRef.current = false;
            if (lastVoiceAtRef.current !== null) lastVoiceAtRef.current = Date.now();
            else answeringSinceRef.current = Date.now();
            setVoiceStatus("Starting microphone...");
            void beginAudioCapture().then((recordingStarted) => {
              setVoiceStatus(microphoneStatus(recordingStarted, startLiveTranscript(recordingStarted)));
            });
          }
        }}>{recording || speech.listening ? "Pause microphone" : "Start microphone"}</button>}
      </div>
    </div>
    {speech.error && <p className="mock-interview-error" role="alert">{speech.error} You can type your answer below.</p>}
    {awayPrompt && <p className="mock-interview-away" role="alert"><strong>{AWAY_PROMPT}</strong> Start answering the question - if nothing is heard in {Math.round(AFTER_PROMPT_END_MS / 1000)} seconds, the interview ends.</p>}
    {silenceHint && <p className="mock-interview-silence-hint" aria-live="polite">{silenceHint}</p>}
    <label className="mock-interview-answer-label" htmlFor="mock-interview-answer">Your answer (voice transcription appears here)</label>
    <textarea id="mock-interview-answer" value={typedAnswer} onChange={(event) => { typedEditedRef.current = true; typedRef.current = event.target.value; setTypedAnswer(event.target.value); }} placeholder="Your answer..." disabled={busy || transcribing} rows={4} />
    <div className="mock-interview-actions"><button type="button" className="btn btn-primary" disabled={busy || transcribing || !canSubmit || secondsLeft === null} onClick={() => { void submitAnswer(activeAnswer); }}>{transcribing ? "Transcribing with OpenAI..." : busy ? "Saving..." : "Submit answer"}</button><button type="button" className="btn btn-outline" disabled={busy || transcribing} onClick={() => { if (window.confirm("Exit this interview? Unanswered questions will not be scored.")) onExit(); }}>Exit interview</button></div>
  </section>;
}
