import { useState, type FormEvent } from "react";

interface NewChatLandingProps {
  onSend: (text: string) => void;
}

export default function NewChatLanding({ onSend }: NewChatLandingProps) {
  const [input, setInput] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    onSend(text);
    setInput("");
  }

  return (
    <section className="view view-chat new-chat-landing active">
      <div className="landing-center">
        <span className="logo-mark landing-logo">⚡</span>
        <h1>What's on the agenda today?</h1>

        <form className="landing-composer glow-border" onSubmit={handleSubmit}>
          <button type="button" className="icon-btn" title="Attach file">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
          <input
            type="text"
            placeholder="Ask anything"
            autoComplete="off"
            autoFocus
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <button type="button" className="icon-btn" title="Voice input">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M12 15a3 3 0 003-3V6a3 3 0 00-6 0v6a3 3 0 003 3z" stroke="currentColor" strokeWidth="1.8" />
              <path d="M19 11a7 7 0 01-14 0M12 18v3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </button>
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
      </div>
    </section>
  );
}
