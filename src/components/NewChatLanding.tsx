import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { audioRecordingSupported } from "../lib/voiceCapture";
import { cancelVoiceConversation, continueVoiceConversation } from "../lib/voiceReply";
import VoiceConversation from "./VoiceConversation";
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
  /** The learner's name, for Boss's spoken greeting. */
  userName?: string;
  /** Opens the chat for a voice conversation right away, so the conversation
   * never has to move from this screen to the chat after the first question. */
  onStartVoice?: () => void;
}

/** Line icons for the agent chips, drawn in each agent's own colour. */
const AGENT_ICONS: Record<string, ReactNode> = {
  codeforge: <path d="M8 6l-6 6 6 6M16 6l6 6-6 6" />,
  aptitude: <path d="M5 20V12M10 20V6M15 20v-9M20 20V9" />,
  "mock-interview": <><path d="M12 15a3 3 0 003-3V6a3 3 0 00-6 0v6a3 3 0 003 3z" /><path d="M19 11a7 7 0 01-14 0M12 18v3" /></>,
  "job-fetch": <><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M9 7V5a2 2 0 012-2h2a2 2 0 012 2v2M3 13h18" /></>,
  capstone: <><path d="M22 9L12 4 2 9l10 5 10-5z" /><path d="M6 11v5c0 1.5 2.7 3 6 3s6-1.5 6-3v-5" /></>,
  communication: <><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0113 0M16 4.5a3.5 3.5 0 010 7M18.5 14a5.5 5.5 0 013 5" /></>,
  "resume-builder": <><path d="M14 3H6a2 2 0 00-2 2v14a2 2 0 002 2h12a2 2 0 002-2V9l-6-6z" /><path d="M14 3v6h6M8 13h8M8 17h6" /></>,
  certificate: <><circle cx="12" cy="9" r="5.5" /><path d="M8.5 13.5L7 21l5-3 5 3-1.5-7.5" /></>,
};

function AgentIcon({ kind, size = 16 }: { kind?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {AGENT_ICONS[kind ?? ""] ?? <circle cx="12" cy="12" r="8" />}
    </svg>
  );
}

const agentLabel = (name: string) => name.replace(/ Agent$/, "");

export default function NewChatLanding({ onSend, onAttachClick, onOpenAgent, userName, onStartVoice }: NewChatLandingProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  // The microphone opens a spoken conversation with the DigiDARA Assistant;
  // its first question starts the chat, where the conversation carries on.
  const [talking, setTalking] = useState(false);
  const voiceSupported = audioRecordingSupported();
  // "Auto-select agent": a typed message goes to DigiDARA, which picks the
  // agent. Choosing an agent in the menu opens that agent's chat.
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!input.trim()) return;
    cancelVoiceConversation();
    onSend(input.trim());
    setInput("");
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

  useEffect(() => {
    if (!menuOpen) return;
    const close = (e: MouseEvent) => { if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false); };
    const escape = (e: KeyboardEvent) => { if (e.key === "Escape") setMenuOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", escape); };
  }, [menuOpen]);

  return (
    <section className="view view-chat new-chat-landing home-landing active">
      <div className="landing-center">
        <div className="home-logo">
          <Logo variant="icon" size={72} />
        </div>
        <h1 className="landing-title">What can I help you with?</h1>
        <p className="home-subtitle">One conversation. The right AI agent for every goal.</p>

        <form className="home-composer" onSubmit={handleSubmit}>
          <textarea
            ref={textareaRef}
            rows={2}
            placeholder="Ask anything, or choose an agent..."
            aria-label="Message"
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
          <div className="home-composer-bar">
            <button type="button" className="home-round-btn" title="Attach file" aria-label="Attach file" onClick={onAttachClick}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </button>
            <div className="home-agent-select" ref={menuRef}>
              <button type="button" className="home-agent-trigger" aria-haspopup="menu" aria-expanded={menuOpen}
                onClick={() => setMenuOpen((open) => !open)}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8L12 3zM18.5 15l.9 2.1 2.1.9-2.1.9-.9 2.1-.9-2.1-2.1-.9 2.1-.9.9-2.1z"
                    fill="currentColor" />
                </svg>
                <span>Auto-select agent</span>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
              {menuOpen && (
                <div className="home-agent-menu" role="menu">
                  <div className="home-agent-menu-note">Type a message and DigiDARA picks the agent, or open one:</div>
                  {LIVE_AGENTS.map((agent) => (
                    <button key={agent.id} type="button" role="menuitem" className="home-agent-option"
                      style={{ ["--agent-color" as string]: agent.color }}
                      onClick={() => { setMenuOpen(false); onOpenAgent(agent.id); }}>
                      <span className="home-chip-icon"><AgentIcon kind={agent.kind} /></span>
                      {agentLabel(agent.name)}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <span className="home-bar-spacer" />
            {voiceSupported && (
              <button type="button" className="home-round-btn" title="Talk with Boss" aria-label="Talk with Boss"
                onClick={() => (onStartVoice ? onStartVoice() : setTalking(true))}>
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M12 15a3 3 0 003-3V6a3 3 0 00-6 0v6a3 3 0 003 3z" stroke="currentColor" strokeWidth="1.8" />
                  <path d="M19 11a7 7 0 01-14 0M12 18v3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                </svg>
              </button>
            )}
            <button type="submit" className="home-send-btn" aria-label="Send" disabled={!input.trim()}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M12 19V5M5 12l7-7 7 7" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
        </form>

        <div className="home-chips">
          {LIVE_AGENTS.map((agent) => (
            <button key={agent.id} type="button" className="home-chip" title={agent.desc}
              style={{ ["--agent-color" as string]: agent.color }}
              onClick={() => onOpenAgent(agent.id)}>
              <span className="home-chip-icon"><AgentIcon kind={agent.kind} /></span>
              {agentLabel(agent.name)}
            </button>
          ))}
        </div>
        <p className="home-hint">Choose an agent or let DigiDARA pick the right one.</p>
      </div>
      <p className="home-disclaimer">AI can make mistakes. Please verify important information.</p>
      {talking && (
        <VoiceConversation messages={[]} typing={false} learnerName={userName} onClose={() => setTalking(false)}
          onSend={(text) => { continueVoiceConversation(); onSend(text); }} />
      )}
    </section>
  );
}
