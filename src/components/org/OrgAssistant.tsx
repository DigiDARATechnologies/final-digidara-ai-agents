import { useEffect, useRef, useState, type FormEvent } from "react";
import useSpeechRecognition from "../../hooks/useSpeechRecognition";
import { transcribeGeneralAudio } from "../../lib/orchestratorApi";
import { speakNatural, stopSpeaking } from "../../lib/voiceEngine";
import { recognitionLocale } from "../../lib/voicePrefs";
import { askAssistant, clearAssistant, fetchAssistantHistory, type AssistantTurn, type OrgFilters } from "../../lib/orgApi";

interface Props {
  orgId: string;
  orgName: string;
  filters: OrgFilters;
  onToast: (message: string) => void;
}

const SUGGESTIONS = [
  "Who needs attention this week?",
  "Compare readiness by department",
  "Which learners have not signed in yet?",
  "Create a join code for 1st year, section A",
];

/** The organization's own assistant: typed or spoken questions about this
 * organization only, answered from its data, with actions it can take. */
export default function OrgAssistant({ orgId, orgName, filters, onToast }: Props) {
  const [turns, setTurns] = useState<AssistantTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [speak, setSpeak] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const speech = useSpeechRecognition(recognitionLocale(), transcribeGeneralAudio, undefined, true);

  useEffect(() => {
    fetchAssistantHistory(orgId).then(setTurns).catch(() => setTurns([])).finally(() => setLoaded(true));
    return () => stopSpeaking();
  }, [orgId]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, busy]);

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    setDraft("");
    setBusy(true);
    setTurns((current) => [...current, { role: "user", content: message, actions: [], created_at: null }]);
    try {
      const result = await askAssistant(orgId, message, filters);
      setTurns((current) => [...current, { role: "assistant", content: result.reply, actions: result.actions, created_at: null }]);
      if (speak) void speakNatural(result.reply, {}, true);
    } catch (err) {
      setTurns((current) => [...current, { role: "assistant", content: (err as Error).message, actions: [], created_at: null }]);
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void send(draft);
  }

  function toggleMic() {
    if (speech.listening) {
      speech.stop();
      return;
    }
    stopSpeaking();
    speech.start((text, final) => {
      if (final) void send(text);
      else setDraft(text);
    }, { autoStopOnSilence: true, silenceMs: 2500 });
  }

  async function clear() {
    if (!window.confirm("Clear this conversation and what the assistant remembers about you?")) return;
    try {
      await clearAssistant(orgId);
      setTurns([]);
      onToast("Conversation cleared.");
    } catch (err) {
      onToast((err as Error).message);
    }
  }

  const activeFilters = Object.entries(filters).filter(([key, value]) => value && key !== "search").map(([, value]) => value);

  return (
    <section className="org-card org-assistant">
      <header className="org-assistant-head">
        <div>
          <h3>{orgName} assistant</h3>
          <span className="rd-muted">Ask about your learners, or ask it to make a code, set a level or check readiness.
            {activeFilters.length > 0 && ` Using your filters: ${activeFilters.join(", ")}.`}</span>
        </div>
        <div className="org-actions">
          <label className="org-toggle">
            <input type="checkbox" checked={speak} onChange={(e) => { setSpeak(e.target.checked); if (!e.target.checked) stopSpeaking(); }} />
            <span>Speak replies</span>
          </label>
          {turns.length > 0 && <button type="button" className="link-btn" onClick={() => void clear()}>Clear</button>}
        </div>
      </header>

      <div className="org-assistant-list" ref={listRef} aria-live="polite">
        {loaded && turns.length === 0 && (
          <div className="org-assistant-empty">
            <p>Answers use only {orgName}'s data. Opening a learner's details here is logged like in the dashboard.</p>
            <div className="org-suggestions">
              {SUGGESTIONS.map((s) => <button key={s} type="button" onClick={() => void send(s)}>{s}</button>)}
            </div>
          </div>
        )}
        {turns.map((turn, index) => (
          <div key={index} className={`org-msg ${turn.role === "user" ? "user" : "agent"}`}>
            <p>{turn.content}</p>
            {turn.actions.length > 0 && (
              <ul className="org-assistant-actions">{turn.actions.map((a) => <li key={a}>✓ {a}</li>)}</ul>
            )}
            {turn.role === "assistant" && (
              <button type="button" className="link-btn org-listen" onClick={() => void speakNatural(turn.content, {}, true)}>Listen</button>
            )}
          </div>
        ))}
        {busy && <div className="org-msg agent org-typing" aria-label="Thinking"><span /><span /><span /></div>}
      </div>

      <form className="org-assistant-input" onSubmit={submit}>
        <input value={draft} maxLength={2000} placeholder={speech.listening ? "Listening…" : speech.transcribing ? "Turning your voice into text…" : `Ask about ${orgName}`}
          onChange={(e) => setDraft(e.target.value)} disabled={busy} />
        {speech.supported && (
          <button type="button" className={`org-mic${speech.listening ? " on" : ""}`} onClick={toggleMic} disabled={busy}
            aria-label={speech.listening ? "Stop listening" : "Speak your question"} aria-pressed={speech.listening}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <rect x="9" y="3" width="6" height="11" rx="3" stroke="currentColor" strokeWidth="1.8" />
              <path d="M5 11a7 7 0 0014 0M12 18v3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </button>
        )}
        <button className="btn btn-primary btn-sm" disabled={busy || !draft.trim()}>Send</button>
      </form>
      {speech.error && <p className="form-error" role="alert">{speech.error}</p>}
    </section>
  );
}
