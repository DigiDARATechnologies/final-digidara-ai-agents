import { useEffect, useRef, useState } from "react";
import useSpeechRecognition from "../hooks/useSpeechRecognition";
import { transcribeGeneralAudio } from "../lib/orchestratorApi";
import { speakNatural, stopSpeaking } from "../lib/voiceEngine";
import type { CapstoneFlowState } from "../lib/capstoneFlow";

/** A pause this long after the student has spoken sends the answer. */
const VIVA_SILENCE_SUBMIT_MS = 5_000;
const MODE_KEY = "digidara_viva_mode";

type VivaMode = "voice" | "typing";

function loadMode(): VivaMode {
  try {
    return localStorage.getItem(MODE_KEY) === "typing" ? "typing" : "voice";
  } catch {
    return "voice";
  }
}

function saveMode(mode: VivaMode) {
  try {
    localStorage.setItem(MODE_KEY, mode);
  } catch {
    // Private mode: the choice lasts for this visit only.
  }
}

function clock(seconds: number): string {
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

interface Props {
  state: CapstoneFlowState;
  busy: boolean;
  onAnswer: (answer: string) => void;
  /** The attempt's 20 minutes ran out. */
  onTimeUp: () => void;
}

/**
 * The Capstone viva, the way the Mock Interview runs: the question is shown
 * and read aloud, then the microphone opens; a 5-second pause after speaking
 * sends the answer (transcribed by OpenAI). Typing in the answer box instead
 * hands control back to the student, who sends it with Submit. The attempt's
 * 20-minute timer is shown throughout. The chat flow itself is unchanged:
 * answers go through the same viva steps as typed ones.
 */
export default function CapstoneVivaPanel({ state, busy, onAnswer, onTimeUp }: Props) {
  const speech = useSpeechRecognition("en-IN", transcribeGeneralAudio, undefined, true);
  const [mode, setMode] = useState<VivaMode>(loadMode);
  const [answer, setAnswer] = useState("");
  const [status, setStatus] = useState("");
  const [countdown, setCountdown] = useState<number | null>(null);
  const [reading, setReading] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState<number | null>(() =>
    state.vivaDeadlineAt ? Math.max(0, Math.ceil((state.vivaDeadlineAt - Date.now()) / 1000)) : null);
  const typedRef = useRef(false);
  const sentRef = useRef(false);
  const timeUpSentRef = useRef(false);
  const onAnswerRef = useRef(onAnswer);
  onAnswerRef.current = onAnswer;
  const onTimeUpRef = useRef(onTimeUp);
  onTimeUpRef.current = onTimeUp;
  const busyRef = useRef(busy);
  busyRef.current = busy;

  const question = state.vivaQuestionText ?? "";
  const questionKey = `${state.vivaSubmissionId}:${state.vivaAttempt}:${state.vivaQuestionId}`;
  const [current, total] = (state.vivaProgress ?? "").split(" of ").map((value) => Number(value) || 0);

  function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sentRef.current || busyRef.current) return;
    sentRef.current = true;
    stopSpeaking();
    speech.cancel();
    onAnswerRef.current(trimmed);
  }

  function startListening() {
    if (sentRef.current || typedRef.current) return;
    setReading(false);
    setStatus("Starting microphone...");
    const started = speech.start((text, final) => {
      if (!final) return;
      setCountdown(null);
      if (sentRef.current) return;
      if (typedRef.current) {
        // The student started typing: their text in the box is the answer.
        return;
      }
      if (text.trim()) {
        setAnswer(text);
        setStatus("Sending your answer...");
        send(text);
      } else {
        setStatus("No answer was heard. Tap Start microphone and answer the question, or type it below.");
      }
    }, {
      autoStopOnSilence: true,
      silenceMs: VIVA_SILENCE_SUBMIT_MS,
      onSilenceCountdown: setCountdown,
    });
    setStatus(started
      ? "Listening - answer the question. Stop talking for 5 seconds and your answer is sent."
      : "The microphone is unavailable. Type your answer below.");
  }

  // Each new question: read it aloud, then open the microphone (voice mode).
  useEffect(() => {
    if (!question) return;
    let active = true;
    sentRef.current = false;
    typedRef.current = false;
    setAnswer("");
    setCountdown(null);
    if (mode !== "voice") {
      setStatus("Type your answer and press Submit.");
      return () => { active = false; };
    }
    setReading(true);
    setStatus("Reading the question aloud...");
    void speakNatural(question, { onEnd: () => { if (active) startListening(); } }, true)
      .then((started) => { if (active && !started) startListening(); });
    return () => {
      active = false;
      stopSpeaking();
      speech.cancel();
    };
    // A new question or a change of mode starts a new voice session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [questionKey, mode]);

  // The attempt's 20-minute timer.
  useEffect(() => {
    timeUpSentRef.current = false;
    if (!state.vivaDeadlineAt) {
      setSecondsLeft(null);
      return;
    }
    const deadline = state.vivaDeadlineAt;
    const tick = () => {
      const left = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
      setSecondsLeft(left);
      if (left === 0 && !timeUpSentRef.current && !busyRef.current) {
        timeUpSentRef.current = true;
        sentRef.current = true;
        stopSpeaking();
        speech.cancel();
        onTimeUpRef.current();
      }
    };
    tick();
    const timer = window.setInterval(tick, 250);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.vivaDeadlineAt]);

  function chooseMode(next: VivaMode) {
    if (next === mode) return;
    saveMode(next);
    setMode(next);
  }

  const listening = speech.listening;
  const timeUp = secondsLeft === 0;
  const locked = busy || sentRef.current || timeUp;
  const voiceStatus = speech.transcribing ? "Turning your answer into text..." : status;

  return <section className="mock-interview-panel capstone-viva-panel" aria-label="Capstone viva">
    <div className="mock-interview-header">
      <div>
        <small>PROJECT VIVA</small>
        <p className="mock-interview-round">Attempt {state.vivaAttempt ?? 1} of {state.vivaAttemptsTotal ?? 3}</p>
      </div>
      {total > 0 && <div className="mock-interview-progress" aria-label={`Question ${current} of ${total}`}>
        <span>{current}/{total}</span>
        <div className="mock-interview-progress-track"><i style={{ width: `${Math.min(100, (current / total) * 100)}%` }} /></div>
      </div>}
      {secondsLeft !== null && <div className={`mock-interview-timer${secondsLeft <= 120 ? " warning" : ""}`} role="timer">
        <span>Time left</span><strong>{clock(secondsLeft)}</strong>
      </div>}
    </div>
    <div className="capstone-viva-mode" role="radiogroup" aria-label="How do you want to answer?">
      <button type="button" role="radio" aria-checked={mode === "voice"} className={`btn ${mode === "voice" ? "btn-primary" : "btn-outline"}`}
        disabled={locked} onClick={() => chooseMode("voice")}>Answer by voice</button>
      <button type="button" role="radio" aria-checked={mode === "typing"} className={`btn ${mode === "typing" ? "btn-primary" : "btn-outline"}`}
        disabled={locked} onClick={() => chooseMode("typing")}>Answer by typing</button>
    </div>
    <div className="mock-interview-question">
      {current > 0 && <span className="mock-interview-question-number" aria-hidden="true">{current}.</span>}
      <span>{question}</span>
    </div>
    {mode === "voice" && <div className={`mock-interview-voice${listening ? " listening" : ""}`}>
      <span className="mock-interview-voice-status" aria-live="polite"><i aria-hidden="true" />{voiceStatus}</span>
      <div>
        {reading && <button type="button" className="btn btn-outline" disabled={locked} onClick={() => { stopSpeaking(); startListening(); }}>Start answering now</button>}
        {!reading && <button type="button" className="btn btn-outline" disabled={locked || speech.transcribing || typedRef.current} onClick={() => {
          if (listening) {
            // Ends the recording now: what was said is transcribed and sent.
            speech.stop();
          } else {
            startListening();
          }
        }}>{listening ? "Send now" : "Start microphone"}</button>}
      </div>
    </div>}
    {mode === "voice" && speech.error && <p className="mock-interview-error" role="alert">{speech.error}</p>}
    {mode === "voice" && countdown !== null && listening && <p className="mock-interview-silence-hint" aria-live="polite">Pause detected - sending your answer in {countdown}s. Keep talking to continue.</p>}
    {timeUp && <p className="mock-interview-error" role="alert">Time's up for this attempt.</p>}
    <label className="mock-interview-answer-label" htmlFor="capstone-viva-answer">
      {mode === "voice" ? "Your answer (to change it, type here and press Submit)" : "Your answer"}
    </label>
    <textarea id="capstone-viva-answer" value={answer} rows={4} placeholder="Your answer..." disabled={locked || speech.transcribing}
      onChange={(event) => {
        if (!typedRef.current) {
          // Typing takes over from the microphone: nothing is sent automatically.
          typedRef.current = true;
          stopSpeaking();
          speech.cancel();
          setReading(false);
          setCountdown(null);
          if (mode === "voice") setStatus("Typing - press Submit when your answer is ready.");
        }
        setAnswer(event.target.value);
      }} />
    <div className="mock-interview-actions">
      <button type="button" className="btn btn-primary" disabled={locked || speech.transcribing || !answer.trim()} onClick={() => send(answer)}>
        {busy ? "Checking..." : "Submit answer"}
      </button>
    </div>
  </section>;
}
