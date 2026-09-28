import { useEffect, useRef, useState } from "react";
import useSpeechRecognition from "../hooks/useSpeechRecognition";
import { downloadMockInterviewReport } from "../lib/mockInterviewApi";
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
  return value == null ? "—" : `${value}/10`;
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
  return `${sentences.slice(0, 277).trimEnd()}…`;
}

export default function MockInterviewPanel({ state, busy, onAnswer, onExit, onPracticeWeakTopics }: Props) {
  const speech = useSpeechRecognition();
  const [spokenAnswer, setSpokenAnswer] = useState("");
  const [typedAnswer, setTypedAnswer] = useState("");
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const [voiceStatus, setVoiceStatus] = useState("");
  const [downloadError, setDownloadError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const submittedRef = useRef(false);
  const spokenRef = useRef("");
  const typedRef = useRef("");
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

  useEffect(() => {
    if (!questionKey) return;
    let active = true;
    let started = false;
    submittedRef.current = false;
    spokenRef.current = "";
    typedRef.current = "";
    const storageKey = `digidara_mock_interview_deadline_${questionKey}`;
    const existingDeadline = Number(sessionStorage.getItem(storageKey));

    function startAnswering() {
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
      setVoiceStatus(speech.supported ? "Starting microphone…" : "Type your answer below");
      if (speech.supported && deadline > Date.now()) {
        const startedListening = speech.start((text) => {
          if (!active || submittedRef.current || !text) return;
          spokenRef.current = text;
          typedRef.current = text;
          setSpokenAnswer(text);
          setTypedAnswer(text);
        });
        setVoiceStatus(startedListening ? "Listening — speak your answer now" : "Type your answer below");
      }
    }
    beginAnswerRef.current = startAnswering;

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
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    };
    // A new question, rather than a parent rerender, starts a new voice session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [questionKey]);

  function submitAnswer(answer: string, timedOut = false) {
    if (!isLive || busy || submittedRef.current) return;
    const finalAnswer = answer.trim();
    if (!finalAnswer && !timedOut) {
      setVoiceStatus("Speak or type an answer before submitting.");
      return;
    }
    submittedRef.current = true;
    speech.stop();
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    sessionStorage.removeItem(`digidara_mock_interview_deadline_${questionKey}`);
    const elapsed = startedAtRef.current ? Math.round((Date.now() - startedAtRef.current) / 1000) : 0;
    onAnswerRef.current(finalAnswer, { timeTakenSec: Math.max(0, Math.min(timeLimit, elapsed)), timedOut: timedOut && !finalAnswer });
  }

  useEffect(() => {
    if (!isLive || secondsLeft === null || submittedRef.current) return;
    const timer = window.setInterval(() => {
      const remaining = Math.max(0, Math.ceil(((deadlineRef.current ?? Date.now()) - Date.now()) / 1000));
      setSecondsLeft(remaining);
      if (remaining === 0) submitAnswer(typedRef.current || spokenRef.current, true);
    }, 250);
    return () => window.clearInterval(timer);
    // The deadline is stable for the mounted question.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [questionKey, secondsLeft !== null, busy]);

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
      <div className="mock-interview-header"><div><small>INTERVIEW COMPLETE</small><h3>Your Interview Report</h3></div></div>
      <div className="mock-interview-scores">{metrics.map(([label, value]) => <div key={label} className="mock-interview-score"><span>{label}</span><strong>{score(value)}</strong></div>)}</div>
      {summary.max_marks != null && <p className="mock-interview-scorecard-total">Correct-answer score: {summary.total_marks ?? 0} / {summary.max_marks} ({summary.max_marks} questions)</p>}
      {summary.feedback && <p className="mock-interview-report-feedback">{compactFeedback(summary.feedback)}</p>}
      {(summary.strengths || summary.weaknesses) && <div className="mock-interview-feedback-grid">
        <div className="mock-interview-strengths"><strong>Strengths</strong>{feedbackPoints(summary.strengths).map((point, index) => <p key={index}>{point}</p>)}</div>
        <div className="mock-interview-weaknesses"><strong>Areas to Improve</strong>{feedbackPoints(summary.weaknesses).map((point, index) => <p key={index}>{point}</p>)}</div>
      </div>}
      <div className="mock-interview-report-actions">
        {Boolean(summary.subject_breakdown?.weak_subjects?.length) && onPracticeWeakTopics && <button type="button" className="btn btn-outline mock-interview-weak-topic-action" onClick={() => onPracticeWeakTopics(summary.subject_breakdown?.weak_subjects || [])} disabled={busy}>Practice Weak Skills</button>}
        <button type="button" className="btn btn-primary" onClick={downloadReport} disabled={downloading}>{downloading ? "Preparing PDF…" : "Download PDF report"}</button>
      </div>
      {downloadError && <p className="mock-interview-error" role="alert">{downloadError}</p>}
    </section>;
  }

  if (!isLive) return null;
  const activeAnswer = typedAnswer.trim() || spokenAnswer.trim();
  const currentQuestion = state.realQuestionIndex ?? state.questionOrder ?? 1;
  const totalQuestions = state.totalQuestions ?? 10;
  const progressPercent = Math.min(100, Math.max(0, (currentQuestion / totalQuestions) * 100));
  return <section className="mock-interview-panel" aria-label="Live mock interview">
    <div className="mock-interview-header"><div><small>LIVE INTERVIEW</small><p className="mock-interview-round">{state.roundType === "hr" ? "HR interview" : state.roleName || state.subject} · {state.difficulty}</p></div>
      <div className="mock-interview-progress" aria-label={`Question ${currentQuestion} of ${totalQuestions}`}><span>{currentQuestion}/{totalQuestions}</span><div className="mock-interview-progress-track"><i style={{ width: `${progressPercent}%` }} /></div></div>
      <div className={`mock-interview-timer${secondsLeft !== null && secondsLeft <= 15 ? " warning" : ""}`} role="timer"><span>Time Left</span><strong>{secondsLeft === null ? "—" : `${String(Math.floor(secondsLeft / 60)).padStart(2, "0")}:${String(secondsLeft % 60).padStart(2, "0")}`}</strong></div>
    </div>
    <div className="mock-interview-question"><span className="mock-interview-question-number" aria-hidden="true">{currentQuestion}.</span><span>{state.question}</span></div>
    <div className={`mock-interview-voice${speech.listening ? " listening" : ""}`}>
      <span className="mock-interview-voice-status" aria-live="polite"><i aria-hidden="true" />{voiceStatus}{speech.listening ? " · Microphone on" : ""}</span>
      <div>
        {secondsLeft === null && <button type="button" className="btn btn-outline" onClick={() => { if ("speechSynthesis" in window) window.speechSynthesis.cancel(); beginAnswerRef.current(); }}>Start answering now</button>}
        {speech.supported && <button type="button" className="btn btn-outline" disabled={busy || secondsLeft === null} onClick={() => {
          if (speech.listening) { speech.stop(); setVoiceStatus("Microphone paused — restart it or type below."); }
          else {
            setVoiceStatus("Starting microphone…");
            const startedListening = speech.start((text) => {
              if (text) {
                spokenRef.current = text;
                typedRef.current = text;
                setSpokenAnswer(text);
                setTypedAnswer(text);
              }
            });
            setVoiceStatus(startedListening ? "Listening — speak your answer now" : "Type your answer below");
          }
        }}>{speech.listening ? "Pause microphone" : "Start microphone"}</button>}
      </div>
    </div>
    {speech.error && <p className="mock-interview-error" role="alert">{speech.error} You can type your answer below.</p>}
    <label className="mock-interview-answer-label" htmlFor="mock-interview-answer">Your answer (voice transcription appears here)</label>
    <textarea id="mock-interview-answer" value={typedAnswer} onChange={(event) => { typedRef.current = event.target.value; setTypedAnswer(event.target.value); }} placeholder="Your answer…" disabled={busy} rows={4} />
    <div className="mock-interview-actions"><button type="button" className="btn btn-primary" disabled={busy || !activeAnswer || secondsLeft === null} onClick={() => submitAnswer(activeAnswer)}>{busy ? "Saving…" : "Submit answer"}</button><button type="button" className="btn btn-outline" disabled={busy} onClick={() => { if (window.confirm("Exit this interview? Unanswered questions will not be scored.")) onExit(); }}>Exit Interview</button></div>
  </section>;
}
