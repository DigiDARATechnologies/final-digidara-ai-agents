import { useEffect, useRef, useState, type FormEvent } from "react";
import useSpeechRecognition from "../hooks/useSpeechRecognition";
import { assistStream } from "../lib/assistApi";
import { refersToScreen, withoutWakeWords } from "../lib/assistText";
import { transcribeGeneralAudio } from "../lib/orchestratorApi";
import { captureScreenshot, SCREENSHOT_HIDE_ATTRIBUTE } from "../lib/screenCapture";
import { createSpeechQueue, stopSpeaking } from "../lib/voiceEngine";
import { readyToSpeak } from "../lib/voiceText";
import { recognitionLocale } from "../lib/voicePrefs";
import { audioRecordingSupported } from "../lib/voiceCapture";
import { BOSS_VOICE_SPEED } from "./VoiceConversation";
import { Logo } from "./Logo";

interface Props {
  agentId: string;
  agentName: string;
  /** The newest lines of the chat on screen, for Boss to read with the screenshot. */
  getContext: () => string;
}

interface Turn {
  role: "user" | "boss";
  text: string;
  /** The screen was attached to this question. */
  screen?: boolean;
}

const HISTORY_TURNS = 6;

/**
 * "Hey Boss" on every screen, on every device: a learner with a doubt in any
 * agent opens Boss, types or says it, optionally lets Boss look at the page
 * (a screenshot of this app only, sent with that one question and not kept),
 * and gets a streamed answer, spoken when the question was spoken. Boss guides
 * and explains; it never acts for the learner, and in a test it gives hints,
 * not answers (the limits are enforced by the server, app/orchestrator/assist.py).
 */
export default function BossAssistant({ agentId, agentName, getContext }: Props) {
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [lookAtScreen, setLookAtScreen] = useState(false);
  const [busy, setBusy] = useState<"" | "looking" | "thinking">("");
  const [error, setError] = useState("");
  const speech = useSpeechRecognition(recognitionLocale(), transcribeGeneralAudio, transcribeGeneralAudio, true);
  const voiceSupported = audioRecordingSupported();
  const listRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const turnsRef = useRef(turns);
  turnsRef.current = turns;

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [turns, busy]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") close(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
    // close() only reads refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function close() {
    abortRef.current?.abort();
    speech.cancel();
    stopSpeaking();
    setBusy("");
    setOpen(false);
  }

  async function ask(raw: string, spoken: boolean) {
    const message = withoutWakeWords(raw) || raw.trim();
    if (!message || busy) return;
    setError("");
    setInput("");
    stopSpeaking();
    const wantsScreen = lookAtScreen || refersToScreen(message);
    const history = turnsRef.current.slice(-HISTORY_TURNS).map((turn) => ({
      role: turn.role === "user" ? ("user" as const) : ("assistant" as const),
      content: turn.text,
    }));
    let screenshot: string | null = null;
    if (wantsScreen) {
      setBusy("looking");
      screenshot = await captureScreenshot();
      if (!screenshot) setError("I could not capture the screen, so I will answer from your words and the chat.");
    }
    setTurns((previous) => [...previous, { role: "user", text: message, screen: Boolean(screenshot) }, { role: "boss", text: "" }]);
    setBusy("thinking");
    const controller = new AbortController();
    abortRef.current = controller;
    // A spoken question is answered aloud, a few words at a time as they arrive.
    const queue = spoken ? createSpeechQueue({ speed: BOSS_VOICE_SPEED }, true) : null;
    let queued = 0;
    const show = (text: string) => setTurns((previous) => [...previous.slice(0, -1), { role: "boss", text }]);
    try {
      const reply = await assistStream({
        message, history, agentId, agentName, context: getContext(), screenshot, voice: spoken,
      }, (text) => {
        show(text);
        if (!queue) return;
        const ready = readyToSpeak(text, queued, queued === 0);
        if (ready.text) { queue.push(ready.text); queued = ready.next; }
      }, controller.signal);
      show(reply);
      if (queue) { queue.push(reply.slice(queued)); queue.end(); }
    } catch (failure) {
      queue?.end();
      if ((failure as Error).name !== "AbortError") {
        setError((failure as Error).message || "Boss could not answer just now. Please try again.");
        setTurns((previous) => (previous[previous.length - 1]?.text === "" ? previous.slice(0, -1) : previous));
      }
    } finally {
      setBusy("");
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void ask(input, false);
  }

  function handleMic() {
    if (speech.listening) {
      speech.stop();
      return;
    }
    stopSpeaking();
    speech.start((text, final) => {
      if (!final) { setInput(text); return; }
      const said = text.trim();
      setInput("");
      if (said) void ask(said, true);
    }, { autoStopOnSilence: true, silenceMs: 1_500, finalFromPreview: true });
  }

  const status = busy === "looking" ? "Looking at your screen..." : busy === "thinking" ? "Thinking..."
    : speech.transcribing ? "Understanding..." : speech.listening ? "Listening..." : "";

  return (
    <>
      {!open && (
        <button type="button" className="boss-fab" {...{ [SCREENSHOT_HIDE_ATTRIBUTE]: "" }} onClick={() => setOpen(true)}
          aria-label="Ask Boss for help with this screen" title="Ask Boss">
          <Logo variant="icon" size={34} />
        </button>
      )}
      {open && (
        <section className="boss-panel" {...{ [SCREENSHOT_HIDE_ATTRIBUTE]: "" }} role="dialog" aria-label="Ask Boss">
          <header className="boss-panel-head">
            <Logo variant="icon" size={28} />
            <div>
              <strong>Boss</strong>
              <span>{agentName ? `Helping you in ${agentName}` : "Here to help"}</span>
            </div>
            <button type="button" className="icon-btn" onClick={close} aria-label="Close Boss">✕</button>
          </header>
          <div className="boss-panel-list" ref={listRef} aria-live="polite">
            {turns.length === 0 && (
              <p className="boss-panel-hint">
                Stuck or have a doubt? Ask me, or say "Hey Boss". Tap the screen button and I will look at this page and
                guide you. I explain and guide; I do not change anything for you, and in a test I give hints, not answers.
              </p>
            )}
            {turns.map((turn, index) => (
              <div key={index} className={`boss-turn ${turn.role}`}>
                {turn.text || <span className="boss-dots" aria-label="Boss is answering"><i /><i /><i /></span>}
                {turn.screen && <em>with your screen</em>}
              </div>
            ))}
            {status && (
              <p className="boss-panel-status">
                <span className="boss-spinner" aria-hidden="true" />
                {status}
              </p>
            )}
            {error && <p className="boss-panel-error" role="alert">{error}</p>}
          </div>
          <form className="boss-panel-bar" onSubmit={handleSubmit}>
            <button type="button" className={`boss-bar-btn${lookAtScreen ? " on" : ""}`} aria-pressed={lookAtScreen}
              onClick={() => setLookAtScreen((value) => !value)}
              title={lookAtScreen ? "Boss will look at your screen" : "Let Boss look at your screen"}
              aria-label="Let Boss look at your screen">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <rect x="3" y="4" width="18" height="13" rx="2" />
                <path d="M8 21h8M12 17v4" />
              </svg>
            </button>
            <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Ask Boss about this screen..."
              aria-label="Your question for Boss" maxLength={1500} />
            {voiceSupported && (
              <button type="button" className={`boss-bar-btn${speech.listening ? " on" : ""}`} onClick={handleMic}
                aria-label={speech.listening ? "Stop listening" : "Speak to Boss"} title="Speak to Boss">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
                  <path d="M12 15a3 3 0 003-3V6a3 3 0 00-6 0v6a3 3 0 003 3z" />
                  <path d="M19 11a7 7 0 01-14 0M12 18v3" />
                </svg>
              </button>
            )}
            <button type="submit" className="boss-send" disabled={!input.trim() || Boolean(busy)} aria-label="Send">
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M12 19V5M5 12l7-7 7 7" />
              </svg>
            </button>
          </form>
        </section>
      )}
    </>
  );
}
