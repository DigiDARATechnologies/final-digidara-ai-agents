import { useEffect, useRef, useState, type FormEvent } from "react";
import useSpeechRecognition from "../hooks/useSpeechRecognition";
import { transcribeGeneralAudio } from "../lib/orchestratorApi";
import { recognitionLocale } from "../lib/voicePrefs";
import { cancelSpokenReply, expectSpokenReply } from "../lib/voiceReply";
import { Logo } from "./Logo";
import { LIVE_AGENTS } from "../data/agents";

interface NewChatLandingProps {
  onSend: (text: string) => void;
  /** No agent/chat exists yet at this screen, so there's nowhere for an
   * attached file to go -- called instead of opening a file picker, so the
   * caller can explain that (e.g. a toast), matching how the main composer
   * already handles attachments being unavailable for the current agent. */
  onAttachClick: () => void;
  /** Starts a chat with the chosen agent. */
  onOpenAgent: (agentId: string) => void;
}

export default function NewChatLanding({ onSend, onAttachClick, onOpenAgent }: NewChatLandingProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  // The DigiDARA Assistant's voice input: recorded, then transcribed with
  // OpenAI on the server, on every device. The words appear in the box while
  // the learner speaks; a pause sends the question, and the reply is spoken.
  const speech = useSpeechRecognition(recognitionLocale(), transcribeGeneralAudio, transcribeGeneralAudio, true);
  const sendOnFinalRef = useRef(false);
  const voiceSessionRef = useRef(0);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!input.trim()) return;
    voiceSessionRef.current += 1;
    if (speech.listening) speech.cancel();
    cancelSpokenReply();
    onSend(input.trim());
    setInput("");
  }

  function handleMicClick() {
    if (speech.listening) {
      // Stops recording: the question is transcribed and sent.
      speech.stop();
      return;
    }
    setInput("");
    sendOnFinalRef.current = true;
    const session = ++voiceSessionRef.current;
    speech.start((text, final) => {
      if (voiceSessionRef.current !== session) return;
      setInput(text);
      if (final && sendOnFinalRef.current && text.trim()) {
        sendOnFinalRef.current = false;
        voiceSessionRef.current += 1;
        expectSpokenReply();
        onSend(text.trim());
        setInput("");
      }
    }, { autoStopOnSilence: true, silenceMs: 3_000 });
  }

  // Same auto-grow fix as the main chat composer (ChatView.tsx) -- a
  // single-line <input> can never hold a newline at all, so Shift+Enter had
  // nothing to do and multi-line paste silently lost its line breaks.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [input]);

  return (
    <section className="view view-chat new-chat-landing active">
      <div className="landing-center">
        <div style={{ marginBottom: "18px" }}>
          <Logo variant="icon" size={96} />
        </div>
        <h1 className="landing-title">What's on the agenda today?</h1>

        <form className="landing-composer glow-border" onSubmit={handleSubmit}>
          <button type="button" className="icon-btn" title="Attach file" onClick={onAttachClick}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
          <textarea
            ref={textareaRef}
            rows={1}
            placeholder={speech.transcribing ? "Transcribing…" : speech.listening ? "Listening… pause or tap the mic to send" : "Ask anything"}
            autoFocus
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                e.currentTarget.form?.requestSubmit();
              }
            }}
          />
          {speech.supported && (
            <button
              type="button"
              className={`icon-btn${speech.listening ? " mic-recording" : ""}`}
              title={speech.listening ? "Stop recording" : "Voice input"}
              aria-label={speech.listening ? "Stop recording" : "Voice input"}
              disabled={speech.transcribing}
              onClick={handleMicClick}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <path d="M12 15a3 3 0 003-3V6a3 3 0 00-6 0v6a3 3 0 003 3z" stroke="currentColor" strokeWidth="1.8" />
                <path d="M19 11a7 7 0 01-14 0M12 18v3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
            </button>
          )}
          <button type="submit" className="icon-btn send-btn" aria-label="Send">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path
                d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </form>
        {speech.error && <div className="mic-error">{speech.error}</div>}

        <div className="landing-agents">
          <div className="landing-agents-label"><span>Start with an agent</span></div>
          <div className="landing-agents-grid">
            {LIVE_AGENTS.map((agent, i) => (
              <button
                key={agent.id}
                type="button"
                className="landing-agent"
                style={{ ["--agent-color" as string]: agent.color, ["--i" as string]: i }}
                onClick={() => onOpenAgent(agent.id)}
              >
                <span className="landing-agent-icon">{agent.icon}</span>
                <span className="landing-agent-text">
                  <b>{agent.name.replace(/ Agent$/, "")}</b>
                  <small>{agent.desc}</small>
                </span>
                <svg className="landing-agent-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M7 17L17 7M9 7h8v8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
