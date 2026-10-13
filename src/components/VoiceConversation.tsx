import { useEffect, useRef, useState } from "react";
import useSpeechRecognition from "../hooks/useSpeechRecognition";
import { transcribeGeneralAudio } from "../lib/orchestratorApi";
import { speakNatural, stopSpeaking } from "../lib/voiceEngine";
import { recognitionLocale } from "../lib/voicePrefs";
import type { ChatMessage } from "../types";
import { Logo } from "./Logo";

/** A pause this long after the learner has spoken sends what they said. */
export const CONVERSATION_PAUSE_MS = 5_000;

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
}

/**
 * The DigiDARA Assistant as a spoken conversation: the logo in the middle
 * listens, and a 5-second pause sends what was said (transcribed by OpenAI);
 * the reply is spoken, then it listens again -- until the learner ends it.
 * The chat carries on behind it, so every turn is still written down there.
 */
export default function VoiceConversation({ messages, typing, onSend, onClose, awaitingReply = false }: Props) {
  const speech = useSpeechRecognition(recognitionLocale(), transcribeGeneralAudio, transcribeGeneralAudio, true);
  const [phase, setPhase] = useState<Phase>(awaitingReply ? "thinking" : "listening");
  const [heard, setHeard] = useState("");
  const [reply, setReply] = useState("");
  const [sendIn, setSendIn] = useState<number | null>(null);
  const orbRef = useRef<HTMLDivElement | null>(null);
  const openRef = useRef(true);
  const messagesRef = useRef(messages);
  messagesRef.current = messages;
  // How many messages there were when the last question was sent: the next
  // agent message after that is its reply.
  const lastUserIndex = messages.map((m) => m.role).lastIndexOf("user");
  const awaitingFromRef = useRef<number | null>(awaitingReply ? Math.max(0, lastUserIndex) : null);

  function setLevel(level: number) {
    orbRef.current?.style.setProperty("--voice-level", level.toFixed(2));
  }

  function listen() {
    if (!openRef.current) return;
    stopSpeaking();
    setPhase("listening");
    setHeard("");
    setSendIn(null);
    speech.start((text, final) => {
      if (!openRef.current) return;
      setHeard(text);
      if (!final) return;
      setSendIn(null);
      setLevel(0);
      const question = text.trim();
      if (!question) {
        // Nothing understood: keep listening (an error is shown meanwhile).
        window.setTimeout(listen, 1_200);
        return;
      }
      awaitingFromRef.current = messagesRef.current.length;
      setPhase("thinking");
      onSend(question);
    }, {
      autoStopOnSilence: true,
      silenceMs: CONVERSATION_PAUSE_MS,
      onSilenceCountdown: setSendIn,
      onAudioLevel: setLevel,
    });
  }

  function speak(text: string) {
    setPhase("speaking");
    setReply(text);
    void speakNatural(text, { onEnd: () => { if (openRef.current) listen(); } }, true)
      .then((started) => { if (!started && openRef.current) listen(); });
  }

  useEffect(() => {
    openRef.current = true;
    if (!awaitingReply) listen();
    return () => {
      openRef.current = false;
      stopSpeaking();
      speech.cancel();
    };
    // Opens once; the loop then drives itself.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // A reply to the question just asked: say it, then listen again.
  useEffect(() => {
    const from = awaitingFromRef.current;
    const last = messages[messages.length - 1];
    if (from === null || typing || !last || last.role !== "agent" || messages.length <= from) return;
    awaitingFromRef.current = null;
    speak(last.text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.length, typing]);

  function handleOrbTap() {
    if (phase === "speaking") {
      // Interrupt the reply and answer straight away.
      stopSpeaking();
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
      : phase === "speaking" ? "Speaking... tap me to interrupt"
        : speech.listening ? sendIn !== null ? `Sending in ${sendIn}s - keep talking to continue` : "Listening... just talk"
          : speech.error ? "Tap the logo to try again" : "Starting microphone...";

  return <div className={`voice-conversation phase-${phase}${speech.listening ? " hearing" : ""}`} role="dialog" aria-label="Voice conversation with DigiDARA">
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
      <p className="voice-conversation-status" aria-live="polite">{status}</p>
      {phase === "listening" && heard && <p className="voice-conversation-heard">“{heard}”</p>}
      {phase !== "listening" && reply && <p className="voice-conversation-reply">{reply.replace(/[*_#`]/g, "")}</p>}
      {speech.error && <p className="voice-conversation-error" role="alert">{speech.error}</p>}
    </div>
  </div>;
}
