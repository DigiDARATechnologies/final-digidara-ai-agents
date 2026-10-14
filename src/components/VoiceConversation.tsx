import { useEffect, useRef, useState } from "react";
import useSpeechRecognition from "../hooks/useSpeechRecognition";
import { transcribeGeneralAudio } from "../lib/orchestratorApi";
import { createSpeechQueue, speakNatural, stopSpeaking, type SpeechQueue } from "../lib/voiceEngine";
import { setVoiceConversationOpen } from "../lib/voiceReply";
import { completeSentences } from "../lib/voiceText";
import { watchForSpeech } from "../lib/voiceActivity";
import { isHoldRequest, joinAnswer, withoutHoldPhrase } from "../lib/holdPhrase";
import { recognitionLocale } from "../lib/voicePrefs";
import type { ChatMessage } from "../types";
import { Logo } from "./Logo";

/** A pause this long after the learner has spoken sends what they said --
 * about a natural conversational turn. "Just a minute" keeps it listening. */
export const CONVERSATION_PAUSE_MS = 2_000;

type Phase = "listening" | "thinking" | "speaking";

interface Props {
  /** The chat's messages; the conversation keeps adding to them. */
  messages: ChatMessage[];
  typing: boolean;
  onSend: (text: string) => void;
  onClose: () => void;
  /** Opened just after a question was sent (from the start screen): wait for
   * its reply and speak it, instead of listening first. */
  awaitingReply?: boolean;
  /** The learner's first name, for Boss's greeting. */
  learnerName?: string;
}

/** What Boss says when the conversation opens. */
export function bossGreeting(name?: string): string {
  const first = (name || "").trim().split(/\s+/)[0];
  return `Hi${first ? ` ${first}` : ""}! I'm Boss, your DigiDARA AI assistant. Ask me anything about DigiDARA and its agents.`;
}

/**
 * Boss (the DigiDARA Assistant) as a spoken conversation: it greets the
 * learner, then the logo in the middle listens, and a 5-second pause sends what was said (transcribed by OpenAI);
 * the reply is spoken, then it listens again -- until the learner ends it.
 * The chat carries on behind it, so every turn is still written down there.
 */
export default function VoiceConversation({ messages, typing, onSend, onClose, awaitingReply = false, learnerName }: Props) {
  const speech = useSpeechRecognition(recognitionLocale(), transcribeGeneralAudio, transcribeGeneralAudio, true);
  const [phase, setPhase] = useState<Phase>(awaitingReply ? "thinking" : "listening");
  const [sendIn, setSendIn] = useState<number | null>(null);
  const orbRef = useRef<HTMLDivElement | null>(null);
  const openRef = useRef(true);
  const messagesRef = useRef(messages);
  messagesRef.current = messages;
  // How many messages there were when the last question was sent: the next
  // agent message after that is its reply.
  const lastUserIndex = messages.map((m) => m.role).lastIndexOf("user");
  const awaitingFromRef = useRef<number | null>(awaitingReply ? Math.max(0, lastUserIndex) : null);
  // The reply being spoken while it streams in: which message, how much of
  // it has been queued, and the queue saying it.
  const replyRef = useRef<{ index: number; queued: number; queue: SpeechQueue } | null>(null);
  // Bumped whenever speech is interrupted: a stale end never starts listening.
  const turnRef = useRef(0);
  // Said before "just a minute": the rest of the question joins it.
  const heldRef = useRef("");

  function setLevel(level: number) {
    orbRef.current?.style.setProperty("--voice-level", level.toFixed(2));
  }

  function listen() {
    if (!openRef.current) return;
    turnRef.current += 1;
    replyRef.current = null;
    stopSpeaking();
    setPhase("listening");
    setSendIn(null);
    speech.start((text, final) => {
      if (!openRef.current || !final) return;
      setSendIn(null);
      setLevel(0);
      const said = text.trim();
      if (said && isHoldRequest(said)) {
        // "Just a minute": keep what came before and carry on listening.
        heldRef.current = joinAnswer(heldRef.current, withoutHoldPhrase(said));
        window.setTimeout(listen, 100);
        return;
      }
      const question = joinAnswer(heldRef.current, said);
      if (!said) {
        // Nothing understood: keep listening (an error is shown meanwhile).
        window.setTimeout(listen, 1_200);
        return;
      }
      heldRef.current = "";
      awaitingFromRef.current = messagesRef.current.length;
      setPhase("thinking");
      onSend(question);
    }, {
      autoStopOnSilence: true,
      silenceMs: CONVERSATION_PAUSE_MS,
      // The live transcript taken after the learner stopped is the answer.
      finalFromPreview: true,
      onSilenceCountdown: setSendIn,
      onAudioLevel: setLevel,
    });
  }

  /** Listen again once this turn's speech ends, unless it was interrupted. */
  function listenAfter(turn: number) {
    return () => { if (openRef.current && turn === turnRef.current) listen(); };
  }

  function speak(text: string) {
    setPhase("speaking");
    const turn = ++turnRef.current;
    void speakNatural(text, { onEnd: listenAfter(turn) }, true);
  }

  useEffect(() => {
    openRef.current = true;
    setVoiceConversationOpen(true);
    // Boss greets first, then listens.
    if (!awaitingReply) speak(bossGreeting(learnerName));
    return () => {
      openRef.current = false;
      setVoiceConversationOpen(false);
      stopSpeaking();
      speech.cancel();
    };
    // Opens once; the loop then drives itself.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The reply to the question just asked: each sentence is spoken as soon as
  // it has been written, then it listens again.
  const last = messages[messages.length - 1];
  useEffect(() => {
    const from = awaitingFromRef.current;
    const index = messages.length - 1;
    if (from === null || !last || last.role !== "agent" || messages.length <= from) return;
    let reply = replyRef.current;
    if (!reply || reply.index !== index) {
      setPhase("speaking");
      const turn = ++turnRef.current;
      reply = { index, queued: 0, queue: createSpeechQueue({ onEnd: listenAfter(turn) }, true) };
      replyRef.current = reply;
    }
    if (!last.streaming && !typing) {
      reply.queue.push(last.text.slice(reply.queued));
      reply.queued = last.text.length;
      reply.queue.end();
      awaitingFromRef.current = null;
      return;
    }
    const ready = completeSentences(last.text, reply.queued);
    if (ready.text) {
      reply.queue.push(ready.text);
      reply.queued = ready.next;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.length, last?.text, last?.streaming, typing]);

  // Talking over Boss interrupts it, like tapping the logo: it stops and
  // listens. Only a voice counts -- not Boss's own echo or a fan.
  useEffect(() => {
    if (phase !== "speaking") return;
    return watchForSpeech(() => {
      if (!openRef.current) return;
      awaitingFromRef.current = null;
      listen();
    });
    // listen() reads refs only; the watch follows the phase.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  function handleOrbTap() {
    if (phase === "speaking") {
      // Interrupt the reply and answer straight away.
      awaitingFromRef.current = null;
      listen();
    } else if (phase === "listening" && speech.listening) {
      // Send now instead of waiting for the pause.
      speech.stop();
    } else if (phase === "listening" && !speech.listening && !speech.transcribing) {
      listen();
    }
  }

  function end() {
    openRef.current = false;
    stopSpeaking();
    speech.cancel();
    onClose();
  }

  const status = speech.transcribing && phase === "listening" ? "Understanding..."
    : phase === "thinking" ? "Thinking..."
      : phase === "speaking" ? "Speaking... start talking or tap me to interrupt"
        : speech.listening ? sendIn !== null ? `Sending in ${sendIn}s - keep talking to continue` : "Listening... just talk"
          : speech.error ? "Tap the logo to try again" : "Starting microphone...";

  return <div className={`voice-conversation phase-${phase}${speech.listening ? " hearing" : ""}`} role="dialog" aria-label="Voice conversation with Boss">
    <button type="button" className="voice-conversation-end" onClick={end}>End voice chat</button>
    <div className="voice-conversation-center">
      <div ref={orbRef} className="voice-conversation-orb">
        <span className="voice-conversation-ring" aria-hidden="true" />
        <span className="voice-conversation-ring second" aria-hidden="true" />
        <button type="button" className="voice-conversation-logo" onClick={handleOrbTap}
          aria-label={phase === "speaking" ? "Interrupt" : speech.listening ? "Send now" : "Talk"}>
          <Logo variant="icon" size={92} />
        </button>
      </div>
      {/* No words on screen: the logo shows what is happening, and the status
          is read out to screen readers only. */}
      <p className="visually-hidden" aria-live="polite">{status}</p>
      {speech.error && <p className="voice-conversation-error" role="alert">{speech.error}</p>}
    </div>
  </div>;
}
