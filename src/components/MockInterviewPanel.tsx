import { useEffect, useRef, useState } from "react";
import useSpeechRecognition from "../hooks/useSpeechRecognition";
import { isMobileVoiceDevice, microphoneErrorMessage } from "../lib/voiceCapture";
import { downloadMockInterviewReport, transcribeMockInterviewAudio } from "../lib/mockInterviewApi";
import { speakBrowserText } from "../lib/browserSpeech";
import type { MockInterviewAnswerTiming, MockInterviewFlowState } from "../lib/mockInterviewFlow";

const TIME_LIMIT_SECONDS = { beginner: 60, intermediate: 90, advanced: 120 } as const;

interface Props {
  state: MockInterviewFlowState;
  busy: boolean;
  onAnswer: (answer: string, timing: MockInterviewAnswerTiming) => void;
  onExit: () => void;
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

  function acceptVoiceTranscript(text: string) {
    if (!text || submittedRef.current) return;
    if (isQuestionEcho(text, state.question)) return;
    spokenRef.current = text;
    setSpokenAnswer(text);
    if (!typedEditedRef.current) {
      typedRef.current = text;
      setTypedAnswer(text);
    }
  }

  function closeAudioStream() {
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
      const recordingStarted = recordingSupported ? await beginAudioCapture() : false;
      const startedListening = startLiveTranscript(recordingStarted);
      setVoiceStatus(microphoneStatus(recordingStarted, startedListening, true));
      return;
    }
    sessionStorage.removeItem(`digidara_mock_interview_deadline_${questionKey}`);
    onAnswerRef.current(finalAnswer, { timeTakenSec: Math.max(0, Math.min(timeLimit, elapsed)), timedOut: timedOut && !finalAnswer });
  }

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
            speech.stop();
            if (mediaRecorderRef.current?.state === "recording") {
              mediaRecorderRef.current.pause();
              setRecording(false);
            }
            setVoiceStatus("Microphone paused - restart it or type below.");
          }
          else {
            setVoiceStatus("Starting microphone...");
            void beginAudioCapture().then((recordingStarted) => {
              setVoiceStatus(microphoneStatus(recordingStarted, startLiveTranscript(recordingStarted)));
            });
          }
        }}>{recording || speech.listening ? "Pause microphone" : "Start microphone"}</button>}
      </div>
    </div>
    {speech.error && <p className="mock-interview-error" role="alert">{speech.error} You can type your answer below.</p>}
    <label className="mock-interview-answer-label" htmlFor="mock-interview-answer">Your answer (voice transcription appears here)</label>
    <textarea id="mock-interview-answer" value={typedAnswer} onChange={(event) => { typedEditedRef.current = true; typedRef.current = event.target.value; setTypedAnswer(event.target.value); }} placeholder="Your answer..." disabled={busy || transcribing} rows={4} />
    <div className="mock-interview-actions"><button type="button" className="btn btn-primary" disabled={busy || transcribing || !canSubmit || secondsLeft === null} onClick={() => { void submitAnswer(activeAnswer); }}>{transcribing ? "Transcribing with OpenAI..." : busy ? "Saving..." : "Submit answer"}</button><button type="button" className="btn btn-outline" disabled={busy || transcribing} onClick={() => { if (window.confirm("Exit this interview? Unanswered questions will not be scored.")) onExit(); }}>Exit interview</button></div>
  </section>;
}
