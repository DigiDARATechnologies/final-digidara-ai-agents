import { useEffect, useRef, useState, type FormEvent } from "react";
import useSpeechRecognition from "../hooks/useSpeechRecognition";
import { assistStream, type AssistAction } from "../lib/assistApi";
import { refersToScreen, withoutWakeWords } from "../lib/assistText";
import { transcribeGeneralAudio } from "../lib/orchestratorApi";
import { captureScreenshot, SCREENSHOT_HIDE_ATTRIBUTE } from "../lib/screenCapture";
import { createSpeechQueue, stopSpeaking } from "../lib/voiceEngine";
import { readyToSpeak } from "../lib/voiceText";
import { recognitionLocale } from "../lib/voicePrefs";
import { audioRecordingSupported } from "../lib/voiceCapture";
import { watchForSpeech } from "../lib/voiceActivity";
import { listenForWakeWord, wakeWordSupported } from "../lib/wakeWord";
import { releaseWarmMicrophone, warmMicrophone } from "../lib/micWarm";
import { isVoiceConversationOpen, onVoiceConversationOpen, openBossVoice } from "../lib/voiceReply";
import { BOSS_VOICE_PACE, BOSS_VOICE_SPEED } from "./VoiceConversation";
import { Logo } from "./Logo";

interface Props {
  agentId: string;
  agentName: string;
  /** The newest lines of the chat on screen, for Boss to read with the screenshot. */
  getContext: () => string;
  /** Opens an agent (its id) or a page ("readiness", "boss") when the learner asks Boss to. */
  onNavigate?: (target: string) => void;
}

interface Turn {
  role: "user" | "boss";
  text: string;
  /** The screen was attached to this question. */
  screen?: boolean;
}

const HISTORY_TURNS = 6;
const WAKE_KEY = "digidara.heyBoss";
// A pause this long after the learner has spoken sends what they said.
const PAUSE_MS = 1_500;
/** "Thanks Boss", "that's all", "bye": the learner is done, so the conversation ends. */
const END_PHRASE = /^(?:ok(?:ay)?[\s,]+)?(?:thanks?(?:\s+you)?(?:\s+boss)?|thank\s+you\s+boss|that'?s\s+all|that\s+is\s+all|bye(?:\s+boss)?|good\s?bye|stop|stop\s+listening|close|exit|end)[\s.!]*$/i;
/** "Close the tab", "please close Boss", "you can close this": Boss closes. */
export const CLOSE_PHRASE = /^(?:(?:ok(?:ay)?|please|now)[\s,]+)*(?:you\s+can\s+|can\s+you\s+)?(?:close|exit|hide|shut)(?:\s+(?:(?:the|this|that|your)\s+)?(?:tab|panel|window|boss|chat|assistant|it|this|yourself)(?:\s+(?:tab|panel|window))?)?(?:[\s,]+(?:please|boss))*[\s.!]*$/i;

function readWakePreference(): boolean {
  try {
    return localStorage.getItem(WAKE_KEY) === "on";
  } catch {
    return false;
  }
}

/**
 * "Hey Boss" on every screen, on every device. Say "Hey Boss" (or tap the Boss
 * button): the panel opens and Boss talks with you continuously, like the
 * general chat's microphone: it listens, answers aloud, listens again, until
 * you say "that's all" or close it. You can talk over Boss to interrupt it.
 *
 * Boss can look at the page (a screenshot of this app only, sent with that one
 * question and not kept). It guides and explains; it never acts for the
 * learner, and in a test it gives hints, not answers (the limits are enforced
 * by the server, app/orchestrator/assist.py).
 */
export default function BossAssistant({ agentId, agentName, getContext, onNavigate }: Props) {
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [lookAtScreen, setLookAtScreen] = useState(false);
  const [busy, setBusy] = useState<"" | "looking" | "thinking">("");
  const [speaking, setSpeaking] = useState(false);
  const [conversation, setConversation] = useState(false);
  const [error, setError] = useState("");
  const [wakeOn, setWakeOn] = useState(readWakePreference);
  // Boss's full voice conversation (the Boss chat) is on screen: it has the
  // microphone, so "Hey Boss" and this button wait until it closes.
  const [bossTalking, setBossTalking] = useState(isVoiceConversationOpen);
  useEffect(() => onVoiceConversationOpen(setBossTalking), []);
  const speech = useSpeechRecognition(recognitionLocale(), transcribeGeneralAudio, transcribeGeneralAudio, true);
  const voiceSupported = audioRecordingSupported();
  const wakeSupported = wakeWordSupported();
  const listRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const turnsRef = useRef(turns);
  turnsRef.current = turns;
  const conversationRef = useRef(false);
  const openRef = useRef(false);
  // The loop runs from callbacks made on earlier renders: it calls the newest functions.
  const askRef = useRef<(raw: string, spoken: boolean) => Promise<void>>(async () => {});
  const listenRef = useRef<() => void>(() => {});

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [turns, busy]);

  // "Hey Boss": waits while Boss is closed; the panel's own microphone takes over once it opens.
  // On Boss's own screens (the new-chat screen, the Boss chat) it opens Boss's
  // voice conversation there instead of this panel.
  useEffect(() => {
    if (!wakeOn || !wakeSupported || open || bossTalking) return;
    return listenForWakeWord((rest) => {
      if (!openBossVoice(rest)) startConversation(rest);
    });
    // startConversation only reads refs and setters.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wakeOn, wakeSupported, open, bossTalking]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") close(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
    // close() only reads refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Talking over Boss interrupts it, and Boss listens.
  useEffect(() => {
    if (!speaking || !conversation) return;
    return watchForSpeech(() => {
      stopSpeaking();
      setSpeaking(false);
      listenRef.current();
    });
  }, [speaking, conversation]);

  function toggleWake() {
    const next = !wakeOn;
    setWakeOn(next);
    try {
      localStorage.setItem(WAKE_KEY, next ? "on" : "off");
    } catch {
      // The choice lasts for this visit only.
    }
  }

  function startConversation(rest = "") {
    setOpen(true);
    openRef.current = true;
    setConversation(true);
    conversationRef.current = true;
    warmMicrophone();
    if (rest) void askRef.current(rest, true);
    else window.setTimeout(() => listenRef.current(), 150);
  }

  function endConversation() {
    conversationRef.current = false;
    setConversation(false);
    speech.cancel();
    stopSpeaking();
    setSpeaking(false);
    releaseWarmMicrophone();
  }

  function close() {
    abortRef.current?.abort();
    endConversation();
    openRef.current = false;
    setBusy("");
    setInput("");
    setOpen(false);
  }

  function listenTurn() {
    if (!conversationRef.current || !openRef.current) return;
    stopSpeaking();
    speech.start((text, final) => {
      if (!conversationRef.current) return;
      if (!final) { setInput(text); return; }
      const said = text.trim();
      setInput("");
      if (!said) {
        // Nothing understood: keep listening.
        window.setTimeout(() => listenRef.current(), 800);
        return;
      }
      if (CLOSE_PHRASE.test(withoutWakeWords(said))) {
        close();
        return;
      }
      if (END_PHRASE.test(withoutWakeWords(said))) {
        endConversation();
        return;
      }
      void askRef.current(said, true);
    }, { autoStopOnSilence: true, silenceMs: PAUSE_MS, finalFromPreview: true });
  }
  listenRef.current = listenTurn;

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
    // A spoken question is answered aloud, a few words at a time as they arrive; then Boss listens again.
    const queue = spoken
      ? createSpeechQueue({
        speed: BOSS_VOICE_SPEED,
        pace: BOSS_VOICE_PACE,
        onStart: () => setSpeaking(true),
        onEnd: () => {
          setSpeaking(false);
          if (closing) close();
          else if (conversationRef.current && openRef.current) window.setTimeout(() => listenRef.current(), 150);
        },
      }, true)
      : null;
    let queued = 0;
    // "Close the tab": Boss says goodbye, then closes. "Open aptitude": it goes there and keeps helping.
    let closing = false;
    const act = (action: AssistAction) => {
      if (action.type === "close") closing = true;
      else onNavigate?.(action.target);
    };
    const show = (text: string) => setTurns((previous) => [...previous.slice(0, -1), { role: "boss", text }]);
    try {
      const reply = await assistStream({
        message, history, agentId, agentName, context: getContext(), screenshot, voice: spoken,
      }, (text) => {
        show(text);
        if (!queue) return;
        const ready = readyToSpeak(text, queued, queued === 0);
        if (ready.text) { queue.push(ready.text); queued = ready.next; }
      }, controller.signal, act);
      show(reply);
      if (queue) { queue.push(reply.slice(queued)); queue.end(); }
      else if (closing) window.setTimeout(close, 1_200);
    } catch (failure) {
      queue?.end();
      if ((failure as Error).name !== "AbortError") {
        setError((failure as Error).message || "Boss could not answer just now. Please try again.");
        setTurns((previous) => (previous[previous.length - 1]?.text === "" ? previous.slice(0, -1) : previous));
        // The conversation carries on after a failed answer.
        if (conversationRef.current && openRef.current) window.setTimeout(() => listenRef.current(), 800);
      }
    } finally {
      setBusy("");
    }
  }
  askRef.current = ask;

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void ask(input, false);
  }

  function handleMic() {
    if (conversation) {
      endConversation();
      return;
    }
    startConversation();
  }

  const working = busy !== "" || (speech.transcribing && conversation);
  const status = busy === "looking" ? "Looking at your screen..." : busy === "thinking" ? "Thinking..."
    : speech.transcribing ? "Understanding..." : speaking ? "Speaking... talk to interrupt"
      : speech.listening ? "Listening... just talk" : conversation ? "Starting microphone..." : "";

  return (
    <>
      {!open && !bossTalking && (
        <button type="button" className={`boss-fab${wakeOn && wakeSupported ? " wake" : ""}`} {...{ [SCREENSHOT_HIDE_ATTRIBUTE]: "" }}
          onClick={() => setOpen(true)}
          aria-label="Ask Boss for help with this screen"
          title={wakeOn && wakeSupported ? 'Ask Boss, or say "Hey Boss"' : "Ask Boss"}>
          <Logo variant="icon" size={34} />
        </button>
      )}
      {open && (
        <section className={`boss-panel${conversation ? " talking" : ""}`} {...{ [SCREENSHOT_HIDE_ATTRIBUTE]: "" }} role="dialog" aria-label="Ask Boss">
          <header className="boss-panel-head">
            <span className={`boss-logo${working ? " working" : ""}`}>
              <Logo variant="icon" size={28} />
              <i className="boss-logo-spinner" aria-hidden="true" />
            </span>
            <div>
              <strong>Boss</strong>
              <span>{agentName ? `Helping you in ${agentName}` : "Here to help"}</span>
            </div>
            {wakeSupported && (
              <button type="button" className={`boss-wake${wakeOn ? " on" : ""}`} onClick={toggleWake} aria-pressed={wakeOn}
                title='Listen for "Hey Boss" while this panel is closed'>
                Hey Boss
              </button>
            )}
            <button type="button" className="icon-btn" onClick={close} aria-label="Close Boss">✕</button>
          </header>
          <div className="boss-panel-list" ref={listRef} aria-live="polite">
            {turns.length === 0 && (
              <p className="boss-panel-hint">
                Stuck or have a doubt? Tap the microphone and just talk: I will listen, answer, and listen again until you say
                "that's all". You can talk over me any time. Tap the screen button and I will look at this page and guide you.
                I explain and guide; I do not change anything for you, and in a test I give hints, not answers.
                {wakeSupported && !wakeOn ? ' Turn on "Hey Boss" above to open me by voice.' : ""}
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
              <button type="button" className={`boss-bar-btn${conversation ? " on" : ""}`} onClick={handleMic}
                aria-pressed={conversation}
                aria-label={conversation ? "Stop the voice conversation" : "Talk to Boss"}
                title={conversation ? "Stop the voice conversation" : "Talk to Boss"}>
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
