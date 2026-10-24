import { useCallback, useEffect, useRef, useState } from "react";
import useSpeechRecognition from "../hooks/useSpeechRecognition";
import {
  downloadKnowledgeReport, finishKnowledgeAttempt, startKnowledgeAttempt, submitKnowledgeAnswer,
  type KnowledgeAttempt, type KnowledgeReport, type LearnerQuestion,
} from "../lib/knowledgeApi";
import { transcribeGeneralAudio } from "../lib/orchestratorApi";
import { speakNatural, stopSpeaking } from "../lib/voiceEngine";
import KnowledgeReportView from "./KnowledgeReportView";
import ProctorGate from "./ProctorGate";
import "./Knowledge.css";

const LETTERS = ["A", "B", "C", "D"];
const READ_KEY = "digidara_kt_read_aloud";
const MODE_KEY = "digidara_kt_answer_mode";
/** A pause this long after speaking sends a spoken answer. */
const SILENCE_SUBMIT_MS = 5_000;

function loadFlag(key: string, fallback: string): string {
  try { return localStorage.getItem(key) ?? fallback; } catch { return fallback; }
}
function saveFlag(key: string, value: string): void {
  try { localStorage.setItem(key, value); } catch { /* Private mode: this visit only. */ }
}
function clock(seconds: number): string {
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

interface Props {
  /** The assessment link's proctored session, already agreed to. */
  sessionId: string;
  title: string;
  onClose: () => void;
}

/**
 * A knowledge test from an organization's assessment link, run like the
 * Mock Interview: one question at a time, read aloud, with a timer. Multiple
 * choice is answered by picking an option; other questions by voice or
 * typing. Then the report: score, feedback and every question's answer.
 */
export default function KnowledgeTestView({ sessionId, title, onClose }: Props) {
  const [report, setReport] = useState<KnowledgeReport | null>(null);
  const [attemptId, setAttemptId] = useState<string | null>(null);
  const [finishing, setFinishing] = useState(false);
  const [finishError, setFinishError] = useState("");
  const finishingRef = useRef(false);

  const finish = useCallback(async (id: string) => {
    if (finishingRef.current) return;
    finishingRef.current = true;
    setFinishing(true);
    setFinishError("");
    try {
      const done = await finishKnowledgeAttempt(id);
      setReport(done.report);
    } catch (failure) {
      finishingRef.current = false;
      setFinishError(failure instanceof Error ? failure.message : "Your answers are saved, but the report could not be made. Try again.");
    } finally {
      setFinishing(false);
    }
  }, []);

  return (
    <div className="kt-screen" role="dialog" aria-modal="true" aria-label={title}>
      <div className="kt-inner">
        {report ? (
          <KnowledgeReportView report={report} onDownload={() => attemptId ? downloadKnowledgeReport({ attemptId }, report.title) : Promise.resolve()} onClose={onClose} />
        ) : finishing ? (
          <section className="mock-interview-panel kt-finishing">
            <span className="kt-spinner" aria-hidden="true" /><p>Checking your answers and preparing your report…</p>
          </section>
        ) : finishError ? (
          <section className="mock-interview-panel kt-finishing">
            <p className="proctor-error" role="alert">{finishError}</p>
            <button type="button" className="btn btn-primary" onClick={() => attemptId && void finish(attemptId)}>Try again</button>
          </section>
        ) : (
          <ProctorGate agentName="knowledge_test_agent" refId={sessionId} sessionId={sessionId} label={title}
            onTerminate={() => { if (attemptId) void finish(attemptId); }}>
            <KnowledgeRunner sessionId={sessionId} onAttempt={setAttemptId} onDone={(id) => void finish(id)} onReport={setReport} onClose={onClose} />
          </ProctorGate>
        )}
      </div>
    </div>
  );
}

function KnowledgeRunner({ sessionId, onAttempt, onDone, onReport, onClose }: {
  sessionId: string; onAttempt: (id: string) => void; onDone: (attemptId: string) => void;
  onReport: (report: KnowledgeReport) => void; onClose: () => void;
}) {
  const [attempt, setAttempt] = useState<KnowledgeAttempt | null>(null);
  const [index, setIndex] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    startKnowledgeAttempt(sessionId).then((next) => {
      if (!alive) return;
      if (next.report) { onReport(next.report); return; }
      onAttempt(next.id);
      setAttempt(next);
      const firstOpen = next.questions.findIndex((q) => !next.answered.includes(q.id));
      if (firstOpen === -1) onDone(next.id);
      else setIndex(firstOpen);
    }).catch((failure) => { if (alive) setError(failure instanceof Error ? failure.message : "The test could not be opened."); });
    return () => { alive = false; };
    // Opened once per session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  if (error) {
    return <section className="mock-interview-panel"><p className="proctor-error" role="alert">{error}</p>
      <button type="button" className="btn btn-outline" onClick={onClose}>Close</button></section>;
  }
  if (!attempt) return <section className="mock-interview-panel kt-finishing"><span className="kt-spinner" aria-hidden="true" /><p>Opening your test…</p></section>;

  const question = attempt.questions[index];
  return (
    <QuestionCard
      key={question.id}
      attempt={attempt}
      question={question}
      number={index + 1}
      total={attempt.questions.length}
      onSubmitted={() => {
        // Questions are answered in order, so the next one is still open.
        if (index + 1 >= attempt.questions.length) onDone(attempt.id);
        else setIndex(index + 1);
      }}
    />
  );
}

function QuestionCard({ attempt, question, number, total, onSubmitted }: {
  attempt: KnowledgeAttempt; question: LearnerQuestion; number: number; total: number; onSubmitted: () => void;
}) {
  const speech = useSpeechRecognition("en-IN", transcribeGeneralAudio, transcribeGeneralAudio, true);
  const [choice, setChoice] = useState<number | null>(null);
  const [answer, setAnswer] = useState("");
  const [secondsLeft, setSecondsLeft] = useState(attempt.seconds_per_question);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [readAloud, setReadAloud] = useState(() => loadFlag(READ_KEY, "on") === "on");
  const [mode, setMode] = useState<"voice" | "typing">(() => (loadFlag(MODE_KEY, "typing") === "voice" ? "voice" : "typing"));
  const [status, setStatus] = useState("");
  const sentRef = useRef(false);
  const startedRef = useRef(Date.now());
  const typedRef = useRef(false);
  const choiceRef = useRef<number | null>(null);
  const answerRef = useRef("");
  const onSubmittedRef = useRef(onSubmitted);
  onSubmittedRef.current = onSubmitted;
  const deadlineRef = useRef(Date.now() + attempt.seconds_per_question * 1000);
  choiceRef.current = choice;
  answerRef.current = answer;
  const isMcq = question.qtype === "mcq";

  const submit = useCallback(async (timedOut = false) => {
    if (sentRef.current) return;
    sentRef.current = true;
    stopSpeaking();
    speech.cancel();
    setSending(true);
    setError("");
    const value = isMcq ? (choiceRef.current === null ? "" : String(choiceRef.current)) : answerRef.current.trim();
    try {
      await submitKnowledgeAnswer(attempt.id, {
        question_id: question.id, answer: value, timed_out: timedOut,
        time_taken: Math.round((Date.now() - startedRef.current) / 1000),
      });
      onSubmittedRef.current();
    } catch (failure) {
      sentRef.current = false;
      setSending(false);
      setError(failure instanceof Error ? failure.message : "Your answer could not be saved. Try again.");
    }
    // speech is stable enough for this; isMcq/question fixed per card.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt.id, question.id, isMcq]);

  // The timer: when it runs out, whatever is chosen or written is sent.
  useEffect(() => {
    const tick = window.setInterval(() => {
      const left = Math.max(0, Math.ceil((deadlineRef.current - Date.now()) / 1000));
      setSecondsLeft(left);
      if (left === 0) {
        window.clearInterval(tick);
        void submit(true);
      }
    }, 250);
    return () => window.clearInterval(tick);
  }, [submit]);

  function startListening() {
    if (sentRef.current || typedRef.current) return;
    setStatus("Starting microphone…");
    const started = speech.start((text, final) => {
      if (!final) {
        if (text.trim() && !typedRef.current) setAnswer(text);
        return;
      }
      if (sentRef.current || typedRef.current) return;
      if (text.trim()) {
        setAnswer(text);
        answerRef.current = text;
        setStatus("Sending your answer…");
        void submit();
      } else {
        setStatus("No answer was heard. Tap Start microphone and try again, or type your answer.");
      }
    }, { autoStopOnSilence: true, silenceMs: SILENCE_SUBMIT_MS });
    setStatus(started ? "Listening - answer the question. Stop talking for 5 seconds to send it." : "The microphone is unavailable. Type your answer below.");
  }

  // Each question is read aloud (if on); a spoken answer starts after it.
  useEffect(() => {
    let active = true;
    const spoken = isMcq ? `${question.question} ${question.options.map((option, i) => `Option ${LETTERS[i]}: ${option}.`).join(" ")}` : question.question;
    if (readAloud) {
      void speakNatural(spoken, { onEnd: () => { if (active && !isMcq && mode === "voice") startListening(); } }, true);
    } else if (!isMcq && mode === "voice") {
      startListening();
    }
    return () => { active = false; stopSpeaking(); speech.cancel(); };
    // Once per question.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question.id]);

  const progress = Math.min(100, ((number - 1) / total) * 100);
  return (
    <section className="mock-interview-panel kt-panel" aria-label={`Question ${number} of ${total}`}>
      <div className="mock-interview-header">
        <div>
          <small>KNOWLEDGE TEST</small>
          <p className="mock-interview-round">{attempt.title}</p>
        </div>
        <div className="mock-interview-progress" aria-label={`Question ${number} of ${total}`}>
          <span>{number}/{total}</span>
          <div className="mock-interview-progress-track"><i style={{ width: `${progress}%` }} /></div>
        </div>
        <div className={`mock-interview-timer${secondsLeft <= 10 ? " warning" : ""}`} role="timer">
          <span>Time left</span><strong>{clock(secondsLeft)}</strong>
        </div>
      </div>

      <div className="kt-toolbar">
        <span className="kt-kind">{isMcq ? "Multiple choice" : "Question and answer"}</span>
        <label className="kt-toggle">
          <input type="checkbox" checked={readAloud} onChange={(e) => { setReadAloud(e.target.checked); saveFlag(READ_KEY, e.target.checked ? "on" : "off"); if (!e.target.checked) stopSpeaking(); }} />
          Read questions aloud
        </label>
      </div>

      <div className="mock-interview-question">
        <span className="mock-interview-question-number" aria-hidden="true">{number}.</span>
        <span>{question.question}</span>
      </div>

      {isMcq ? (
        <div className="kt-options" role="radiogroup" aria-label="Choose one answer">
          {question.options.map((option, i) => (
            <button key={i} type="button" role="radio" aria-checked={choice === i} disabled={sending}
              className={`kt-option${choice === i ? " selected" : ""}`} onClick={() => setChoice(i)}>
              <b>{LETTERS[i]}</b><span>{option}</span>
            </button>
          ))}
        </div>
      ) : (
        <>
          <div className="capstone-viva-mode" role="radiogroup" aria-label="How do you want to answer?">
            {(["voice", "typing"] as const).map((value) => (
              <button key={value} type="button" role="radio" aria-checked={mode === value} disabled={sending}
                className={`btn ${mode === value ? "btn-primary" : "btn-outline"}`}
                onClick={() => {
                  setMode(value);
                  saveFlag(MODE_KEY, value);
                  if (value === "typing") { speech.cancel(); setStatus(""); } else { typedRef.current = false; stopSpeaking(); startListening(); }
                }}>
                {value === "voice" ? "Answer by voice" : "Answer by typing"}
              </button>
            ))}
          </div>
          {mode === "voice" && (
            <div className={`mock-interview-voice${speech.listening ? " listening" : ""}`}>
              <span className="mock-interview-voice-status" aria-live="polite"><i aria-hidden="true" />{speech.transcribing ? "Turning your answer into text…" : status}</span>
              <div>
                <button type="button" className="btn btn-outline" disabled={sending || speech.transcribing}
                  onClick={() => (speech.listening ? speech.stop() : (stopSpeaking(), startListening()))}>
                  {speech.listening ? "Send now" : "Start microphone"}
                </button>
              </div>
            </div>
          )}
          {mode === "voice" && speech.error && <p className="mock-interview-error" role="alert">{speech.error}</p>}
          <label className="mock-interview-answer-label" htmlFor="kt-answer">Your answer</label>
          <textarea id="kt-answer" rows={5} value={answer} placeholder="Your answer…" disabled={sending || speech.transcribing}
            onChange={(e) => {
              if (!typedRef.current) { typedRef.current = true; speech.cancel(); stopSpeaking(); }
              setAnswer(e.target.value);
            }} />
        </>
      )}

      {error && <p className="mock-interview-error" role="alert">{error}</p>}
      <div className="mock-interview-actions">
        <button type="button" className="btn btn-primary" disabled={sending || (isMcq ? choice === null : !answer.trim())} onClick={() => void submit()}>
          {sending ? "Saving…" : number === total ? "Submit and finish" : "Submit answer"}
        </button>
      </div>
      <p className="kt-hint">You cannot go back to a question once you submit it. When the time runs out, your answer so far is sent.</p>
    </section>
  );
}
