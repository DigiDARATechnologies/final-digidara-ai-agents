import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import type { Agent, Chat, ChatOption, User } from "../types";
import { DEFAULT_AGENT, findAgent } from "../data/agents";
import ConnectorPill, { type DifficultyPickerProps } from "./ConnectorPill";
import AttachMenu from "./AttachMenu";
import useSpeechRecognition from "../hooks/useSpeechRecognition";
import { unlockSpeechSynthesis } from "../lib/browserSpeech";
import { renderMessageText } from "../lib/messageText";

interface ChatViewProps {
  chat: Chat;
  agent: Agent;
  user: User;
  typing: boolean;
  /** Optional agent-specific progress text in the shared typing indicator. */
  typingLabel?: string;
  /** Locks the normal composer for agent flows that must not accept a second
   * turn while their backend is generating or grading. */
  composerDisabled?: boolean;
  /** A live interview supplies its own voice and typed-answer controls. */
  hideComposer?: boolean;
  onBack: () => void;
  onSend: (text: string, editIndex?: number, internal?: boolean, displayText?: string) => void;
  /** `value` is the internal action; `label` is what the learner sees. */
  onChooseOption: (value: string, label?: string) => void;
  /** Replaces the user message at `index` with `newText` and discards
   * everything after it, resuming the flow from that point ... see
   * App.tsx's sendMessage(text, editIndex) for how the resume actually
   * works. Absent means editing isn't offered (e.g. no host wired it up). */
  onEditMessage?: (index: number, newText: string) => void;
  attachEnabled: boolean;
  /** File input `accept` string ... varies per agent (Capstone wants
   * `.docx,.zip`; Resume Builder wants resume documents). */
  attachAccept?: string;
  pendingFiles: File[];
  onAttachFiles: (files: FileList) => void;
  onRemovePendingFile?: (index: number) => void;
  onAttachDisabled: () => void;
  /** When set, the composer becomes a multi-line code editor with Run/Submit
   * buttons instead of the normal single-line input + send button. */
  codeMode?: boolean;
  codeSeed?: string;
  codeBusy?: boolean;
  onRunCode?: (code: string) => void;
  onSubmitCode?: (code: string) => void;
  /** When set, the composer becomes a resizable multi-line textarea instead
   * of the normal single-line input ... needed for pasting a full resume or a
   * job description, since a single-line input silently loses newlines. */
  multilineMode?: boolean;
  multilinePlaceholder?: string;
  multilineSubmitLabel?: string;
  multilineClassName?: string;
  multilineWordTarget?: number;
  /** ChatGPT/Claude-style header pill: agent status, its pending task (if
   * any), and ... for agents that have one ... a quick per-agent option
   * (Capstone's project difficulty). Absent for the general chat. */
  connectorStatus?: string;
  connectorPendingTask?: string | null;
  connectorDifficultyPicker?: DifficultyPickerProps;
  connectorQuickActions?: ChatOption[];
  onConnectorQuickAction?: (value: string) => void;
  dailyChallengeStatus?: "pending" | "completed";
  onDailyChallenge?: () => void;
  immersiveSpeaking?: boolean;
  /** Pronunciation uses microphone energy detection to stop after speech. */
  autoStopVoiceOnSilence?: boolean;
  /** Extra panel rendered inside the latest agent message, above its text ...
   * used by the Aptitude Trainer Agent for question controls. */
  /** Modal shown after a certificate exam is generated and before Question 1. */
  certificateExamInstructions?: {
    topic: string;
    totalQuestions: number;
    onStart: () => void;
  };
  /** Prominent, exam-only countdown shown in the chat header. */
  certificateExamTimer?: {
    secondsLeft: number;
    currentQuestion: number;
    totalQuestions: number;
  };
  /** Extra panel rendered above the message list ... used by the Aptitude
   * Trainer Agent to show its practice controls alongside the chat. */
  contextPanel?: ReactNode;
}

export default function ChatView({
  chat,
  agent,
  user,
  typing,
  typingLabel,
  composerDisabled = false,
  hideComposer = false,
  onBack,
  onSend,
  onChooseOption,
  onEditMessage,
  attachEnabled,
  attachAccept = ".docx,.zip",
  pendingFiles,
  onAttachFiles,
  onRemovePendingFile,
  onAttachDisabled,
  codeMode = false,
  codeSeed = "",
  codeBusy = false,
  onRunCode,
  onSubmitCode,
  multilineMode = false,
  multilinePlaceholder = "Paste text here...",
  multilineSubmitLabel = "Send",
  multilineClassName = "",
  multilineWordTarget,
  connectorStatus,
  connectorPendingTask,
  connectorDifficultyPicker,
  connectorQuickActions,
  onConnectorQuickAction,
  dailyChallengeStatus,
  onDailyChallenge,
  immersiveSpeaking,
  autoStopVoiceOnSilence = false,
  certificateExamInstructions,
  certificateExamTimer,
  contextPanel,
}: ChatViewProps) {
  const [input, setInput] = useState("");
  const [code, setCode] = useState(codeSeed);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState("");
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const [agentSpeaking, setAgentSpeaking] = useState(false);
  const [inputError, setInputError] = useState("");
  const copiedTimerRef = useRef<number | undefined>(undefined);
  const messagesRef = useRef<HTMLDivElement>(null);
  const composerTextareaRef = useRef<HTMLTextAreaElement>(null);
  const speech = useSpeechRecognition();
  // Recognition is `continuous: true`, so it keeps listening in the
  // background after Send unless explicitly stopped ... and a result that was
  // already in flight can still land *after* stop() and repopulate the box
  // right after it was cleared. Bumping this on every stop/submit lets the
  // result callback recognize and drop those now-stale updates.
  const voiceSessionRef = useRef(0);
  const silenceTimerRef = useRef<number | undefined>(undefined);

  function handleMicClick() {
    if (speech.listening) {
      voiceSessionRef.current += 1;
      speech.stop();
      return;
    }
    setInput("");
    const session = ++voiceSessionRef.current;
    speech.start((text) => {
      if (voiceSessionRef.current !== session) return;
      setInput(text);
    }, { autoStopOnSilence: autoStopVoiceOnSilence });
  }

  useEffect(() => {
    const box = messagesRef.current;
    if (box) box.scrollTop = box.scrollHeight;
  }, [chat.messages.length, typing]);

  useEffect(() => {
    setCode(codeSeed);
  }, [codeSeed]);

  useEffect(() => () => window.clearTimeout(copiedTimerRef.current), []);

  async function handleCopy(index: number, text: string) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      return; // Clipboard access denied/unavailable ... silently skip rather than show a false "Copied".
    }
    setCopiedIndex(index);
    window.clearTimeout(copiedTimerRef.current);
    copiedTimerRef.current = window.setTimeout(() => setCopiedIndex(null), 1500);
  }

  function startEdit(index: number, text: string) {
    setEditingIndex(index);
    setEditDraft(text);
  }

  function cancelEdit() {
    setEditingIndex(null);
    setEditDraft("");
  }

  function saveEdit(index: number) {
    const text = editDraft.trim();
    setEditingIndex(null);
    setEditDraft("");
    if (!text || !onEditMessage) return;
    onEditMessage(index, text);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text && pendingFiles.length === 0) {
      setInputError(multilineMode ? "Please write your paragraph before submitting. ✍️" : "Please enter a message before sending.");
      return;
    }
    setInputError("");
    voiceSessionRef.current += 1;
    if (speech.listening) speech.stop();
    onSend(input);
    setInput("");
  }

  // The default composer is a <textarea rows={1}> that grows with content
  // (up to a CSS-capped max-height, then scrolls) instead of a single-line
  // <input> ... a plain <input> can never hold a real newline at all, which is
  // why Shift+Enter had nothing to do and pasted multi-line text silently
  // lost its line breaks. Re-measured on every keystroke/paste/Send.
  useEffect(() => {
    const el = composerTextareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [input]);

  const activeSpeakingPrompt = [...chat.messages].reverse().find((message) => message.role === "agent")?.text || "Speak when you are ready.";

  useEffect(() => {
    window.clearTimeout(silenceTimerRef.current);
    window.speechSynthesis?.cancel();
    setAgentSpeaking(false);
    if (!immersiveSpeaking || typing || !speech.supported) {
      if (speech.listening) speech.stop();
      return;
    }

    let latestTranscript = "";
    let observedTranscript = "";
    let lastSpeechAt = 0;
    let submitted = false;
    let silenceCheck: number | undefined;
    const session = ++voiceSessionRef.current;

    const submitSpokenTurn = () => {
      if (submitted || voiceSessionRef.current !== session || !latestTranscript) return;
      submitted = true;
      voiceSessionRef.current += 1;
      window.clearInterval(silenceCheck);
      speech.stop();
      onSend(latestTranscript);
      setInput("");
    };

    const beginListening = () => {
      if (submitted || voiceSessionRef.current !== session) return;
      setAgentSpeaking(false);
      setInput("");
      speech.start((text) => {
        if (voiceSessionRef.current !== session || submitted) return;
        const next = text.trim();
        latestTranscript = next;
        setInput(text);
        if (next && next !== observedTranscript) {
          observedTranscript = next;
          lastSpeechAt = Date.now();
        }
      });
      silenceCheck = window.setInterval(() => {
        if (latestTranscript && lastSpeechAt && Date.now() - lastSpeechAt >= 3000) submitSpokenTurn();
      }, 200);
    };

    if ("speechSynthesis" in window && "SpeechSynthesisUtterance" in window) {
      const utterance = new SpeechSynthesisUtterance(activeSpeakingPrompt.replace(/[...]/g, " "));
      utterance.rate = 0.96;
      utterance.pitch = 1;
      utterance.onstart = () => setAgentSpeaking(true);
      utterance.onend = beginListening;
      utterance.onerror = beginListening;
      window.speechSynthesis.speak(utterance);
    } else {
      beginListening();
    }

    return () => {
      submitted = true;
      window.clearInterval(silenceCheck);
      window.speechSynthesis?.cancel();
      setAgentSpeaking(false);
      if (voiceSessionRef.current === session) voiceSessionRef.current += 1;
      speech.stop();
    };
    // A new coach prompt is spoken, then hands control back to recognition.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [immersiveSpeaking, typing, activeSpeakingPrompt]);

  return (
    <section className={`view view-chat active${immersiveSpeaking ? " immersive-speaking" : ""}`} id="view-chat">
      <div className="chat-header">
        <button className="icon-btn" onClick={onBack} aria-label="Back">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M15 18l-6-6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        <span className="avatar chat-agent-avatar" style={{ background: agent.color || "var(--accent-grad)" }}>
          {agent.icon}
        </span>
        <div className="chat-agent-meta">
          <div className="chat-agent-name">{agent.name}</div>
          <div className="chat-agent-status">
            <span className="status-dot small" />
            Online
          </div>
        </div>
        {connectorStatus && (
          <ConnectorPill
            agentIcon={agent.icon}
            agentColor={agent.color}
            agentName={agent.name}
            status={connectorStatus}
            pendingTask={connectorPendingTask}
            difficultyPicker={connectorDifficultyPicker}
            quickActions={connectorQuickActions}
            onQuickAction={onConnectorQuickAction}
          />
        )}
        {dailyChallengeStatus && (
          <button type="button" className={`daily-challenge-pill ${dailyChallengeStatus}`} onClick={onDailyChallenge}>
            <span>📅</span><span>Daily Challenge</span>
            <i>{dailyChallengeStatus === "completed" ? "Completed" : "Pending"}</i>
          </button>
        )}
        {certificateExamTimer && (
          <div className="certificate-timer" aria-label="Exam timing">
            <span>Time Remaining</span>
            <strong>{String(Math.floor(certificateExamTimer.secondsLeft / 60)).padStart(2, "0")}:{String(certificateExamTimer.secondsLeft % 60).padStart(2, "0")}</strong>
            <small>Question {certificateExamTimer.currentQuestion} of {certificateExamTimer.totalQuestions}</small>
          </div>
        )}
      </div>

      <div className="chat-messages" ref={messagesRef}>
        {immersiveSpeaking && <div className="speaking-stage"><div className="speaking-stage-copy"><span>Speaking Practice</span><h2>{activeSpeakingPrompt}</h2><p>{typing ? "Coach is preparing the next question..." : agentSpeaking ? "Coach is speaking..." : speech.listening ? "Listening automatically ... sends after 3 seconds of silence" : "Starting conversation..."}</p></div><button type="button" aria-label={speech.listening ? "Stop listening" : "Start speaking"} className={`speaking-orb${speech.listening ? " listening" : ""}`} onClick={handleMicClick} /><button type="button" className="speaking-end" onClick={() => onChooseOption("end_session")}>End Session</button></div>}
        {!immersiveSpeaking && chat.messages.map((m, i) => {
          const msgAgent = findAgent(chat.agentId) || DEFAULT_AGENT;
          const rawOptions = agent.kind === "communication"
            ? m.options?.filter((option) => !["daily_challenge", "dashboard", "history"].includes(option.value))
            : m.options;
          const visibleOptions = rawOptions?.filter(
            (opt) => opt && typeof opt.label === "string" && opt.label.trim().length > 1 && opt.label.trim() !== "."
          );
          const optionsActive = m.role === "agent" && !!visibleOptions?.length && i === chat.messages.length - 1 && !typing;
          const isEditing = editingIndex === i;
          const hasContextPanel = m.role === "agent" && i === chat.messages.length - 1 && !!contextPanel;
          return (
            <div className={`msg ${m.role === "user" ? "user" : "agent"}${agent.kind === "mock-interview" ? " mock-interview-msg" : ""}`} key={i}>
              <span
                className="avatar"
                style={{ background: m.role === "user" ? "var(--accent-grad)" : msgAgent.color || "var(--accent-grad)" }}
              >
                {m.role === "user" ? user.initial : msgAgent.icon}
              </span>
              <div className={`msg-content${hasContextPanel ? agent.kind === "mock-interview" ? " mock-interview-question-section" : " aptitude-question-section" : ""}`}>
                {isEditing ? (
                  <div className="bubble-edit">
                    <textarea
                      className="bubble-edit-textarea"
                      value={editDraft}
                      autoFocus
                      onChange={(e) => setEditDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          saveEdit(i);
                        } else if (e.key === "Escape") {
                          cancelEdit();
                        }
                      }}
                    />
                    <div className="bubble-edit-actions">
                      <button type="button" className="btn btn-outline" onClick={cancelEdit}>Cancel</button>
                      <button type="button" className="btn btn-primary" disabled={!editDraft.trim()} onClick={() => saveEdit(i)}>
                        Save &amp; submit
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    {hasContextPanel && contextPanel}
                    <div className="bubble">{renderMessageText(m.text)}</div>
                    {!!visibleOptions?.length && (
                      <div className="chat-options">
                        {visibleOptions.map((option) => option.href ? (
                          <a key={option.value} className="chat-option-link" href={option.href} download={option.download ?? ""}>
                            <strong>{option.label}</strong>
                            {option.description && <span>{option.description}</span>}
                          </a>
                        ) : (
                          <button key={option.value} type="button" disabled={!optionsActive} onClick={() => { if (agent.kind === "mock-interview") unlockSpeechSynthesis(); onChooseOption(option.value, option.label); }}>
                            <strong>{option.label}</strong>
                            {option.description && <span>{option.description}</span>}
                          </button>
                        ))}
                      </div>
                    )}
                    <div className="msg-footer">
                      <div className="msg-time">{m.time}</div>
                      <div className="msg-actions">
                        <button type="button" className="msg-action-btn" title="Copy" onClick={() => handleCopy(i, m.text)}>
                          {copiedIndex === i ? "Copied" : "Copy"}
                        </button>
                        {m.role === "user" && onEditMessage && (
                          <button type="button" className="msg-action-btn" title="Edit" disabled={typing} onClick={() => startEdit(i, m.text)}>
                            Edit
                          </button>
                        )}
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="chat-typing" hidden={!typing}>
        <span className="avatar chat-agent-avatar small" style={{ background: agent.color || "var(--accent-grad)" }}>
          {agent.icon}
        </span>
        <div className="typing-bubble">
          <span />
          <span />
          <span />
        </div>
        {typingLabel && <span className="typing-label">{typingLabel}</span>}
      </div>

      {certificateExamInstructions && (
        <div className="certificate-instructions-backdrop" role="dialog" aria-modal="true" aria-labelledby="certificate-instructions-title">
          <section className="certificate-instructions-modal">
            <div className="certificate-instructions-icon">...</div>
            <p className="certificate-instructions-eyebrow">Certification exam ready</p>
            <h2 id="certificate-instructions-title">{certificateExamInstructions.topic} Certification</h2>
            <p className="certificate-instructions-lead">Read these instructions before beginning your {certificateExamInstructions.totalQuestions}-question exam.</p>
            <ul>
              <li><strong>3 minutes per question.</strong> When time ends, the question is marked incorrect and the exam continues.</li>
              <li><strong>Stay on this tab.</strong> You receive warnings; a third tab switch closes the exam as failed.</li>
              <li><strong>Answer every question.</strong> You need a score of 70% or more to pass.</li>
              <li><strong>Certificate on passing.</strong> Your official PDF certificate is issued automatically after a passing result.</li>
            </ul>
            <button type="button" className="certificate-start-button" onClick={certificateExamInstructions.onStart}>
              Start Exam
            </button>
          </section>
        </div>
      )}

      {pendingFiles.length > 0 && (
        <div className="attach-chips">
          {pendingFiles.map((f, i) => (
            <span className="attach-chip" key={`${f.name}-${i}`}>
              📎 {f.name}
              {onRemovePendingFile && (
                <button
                  type="button"
                  className="attach-chip-remove"
                  onClick={() => onRemovePendingFile(i)}
                  title="Remove attachment"
                  aria-label={`Remove ${f.name}`}
                >
                  ✕
                </button>
              )}
            </span>
          ))}
        </div>
      )}

      {hideComposer ? null : codeMode ? (
        <div className="code-composer">
          <textarea
            className="code-editor"
            spellCheck={false}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Write your solution here..."
          />
          <div className="code-composer-actions">
            <button type="button" className="btn btn-outline" disabled={codeBusy} onClick={() => onRunCode?.(code)}>
              {codeBusy ? "Running..." : "... Run public tests"}
            </button>
            <button type="button" className="btn btn-primary" disabled={codeBusy} onClick={() => onSubmitCode?.(code)}>
              {codeBusy ? "Submitting..." : "... Submit solution"}
            </button>
          </div>
        </div>
      ) : multilineMode ? (
        <form className={`paste-composer ${multilineClassName}`.trim()} onSubmit={handleSubmit}>
          <textarea
            className="paste-textarea"
            placeholder={multilinePlaceholder}
            value={input}
            disabled={composerDisabled}
            onChange={(e) => { setInput(e.target.value); if (inputError) setInputError(""); }}
            onKeyDown={(e) => {
              // Enter sends, matching every other composer in this app;
              // Shift+Enter is left alone so the textarea's own default
              // behavior inserts a real newline instead.
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (!composerDisabled) e.currentTarget.form?.requestSubmit();
              }
            }}
          />
          {multilineWordTarget && (
            <div className="writing-word-count">Words: {input.trim() ? input.trim().split(/\s+/).length : 0} / {multilineWordTarget}</div>
          )}
          {inputError && <p className="composer-input-error" role="alert">{inputError}</p>}
          <div className="paste-composer-actions">
            {attachEnabled && (
              <AttachMenu
                enabled={attachEnabled}
                documentAccept={attachAccept}
                onFiles={onAttachFiles}
                onDisabled={onAttachDisabled}
                variant="text"
              />
            )}
            <button type="submit" className="btn btn-primary" disabled={composerDisabled || (!input.trim() && pendingFiles.length === 0)}>{multilineSubmitLabel}</button>
          </div>
        </form>
      ) : (
        <form className="composer" onSubmit={handleSubmit}>
          <AttachMenu
            enabled={attachEnabled}
            documentAccept={attachAccept}
            onFiles={onAttachFiles}
            onDisabled={onAttachDisabled}
            multiple
          />
          <textarea
            ref={composerTextareaRef}
            rows={1}
            placeholder="Message DigiDARA..."
            value={input}
            disabled={composerDisabled}
            onChange={(e) => { setInput(e.target.value); if (inputError) setInputError(""); }}
            onKeyDown={(e) => {
              // Enter sends; Shift+Enter is left alone so the textarea's own
              // default behavior inserts a real newline instead.
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (!composerDisabled) e.currentTarget.form?.requestSubmit();
              }
            }}
          />
          {speech.supported && (
            <button
              type="button"
              className={`icon-btn${speech.listening ? " mic-recording" : ""}`}
              title={speech.listening ? "Stop recording" : "Voice input"}
              onClick={handleMicClick}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <path d="M12 15a3 3 0 003-3V6a3 3 0 00-6 0v6a3 3 0 003 3z" stroke="currentColor" strokeWidth="1.8" />
                <path d="M19 11a7 7 0 01-14 0M12 18v3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
            </button>
          )}
          <button type="submit" disabled={composerDisabled || (!input.trim() && pendingFiles.length === 0)} className="icon-btn send-btn" aria-label="Send">
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
      )}
      {!codeMode && !multilineMode && autoStopVoiceOnSilence && speech.listening && (
        <div className="voice-capture-status" role="status">Listening… I’ll stop automatically after you finish speaking.</div>
      )}
      {!codeMode && !multilineMode && speech.error && <div className="mic-error">{speech.error}</div>}
    </section>
  );
}


