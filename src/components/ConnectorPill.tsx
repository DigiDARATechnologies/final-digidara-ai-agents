import { useEffect, useRef, useState } from "react";
import type { ChatOption } from "../types";

export type ProjectDifficultyLevel = "easy" | "medium" | "hard";

export interface DifficultyPickerProps {
  value: ProjectDifficultyLevel;
  onChange: (value: ProjectDifficultyLevel) => void;
}

interface ConnectorPillProps {
  agentIcon: string;
  agentColor: string;
  agentName: string;
  status: string;
  pendingTask?: string | null;
  difficultyPicker?: DifficultyPickerProps;
  /** A jump-to menu (e.g. Communication Coach's Daily Challenge/Speaking/
   * Writing/Pronunciation/My Progress/History) shown in the dropdown so it's
   * reachable without scrolling back to the chat bubble that first offered
   * it. */
  quickActions?: ChatOption[];
  onQuickAction?: (value: string) => void;
}

const DIFFICULTY_LABELS: Record<ProjectDifficultyLevel, string> = {
  easy: "Easy",
  medium: "Medium",
  hard: "Hard",
};

/** A ChatGPT/Claude-style pill near the chat header: at a glance, which
 * agent this is, its current status/pending task, and — for agents that
 * have one — a quick per-agent option (Capstone's project difficulty). */
export default function ConnectorPill({
  agentIcon,
  agentColor,
  agentName,
  status,
  pendingTask,
  difficultyPicker,
  quickActions,
  onQuickAction,
}: ConnectorPillProps) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("click", onDocClick);
    return () => document.removeEventListener("click", onDocClick);
  }, [open]);

  return (
    <div className="connector-wrap" ref={wrapRef}>
      <button
        type="button"
        className="connector-pill"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
      >
        <span className="connector-pill-icon" style={{ background: agentColor }}>{agentIcon}</span>
        <span>{difficultyPicker ? `Level: ${DIFFICULTY_LABELS[difficultyPicker.value]}` : status}</span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
          <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      <div className={`connector-panel dropdown-panel${open ? " open" : ""}`}>
        <div className="dropdown-head">{agentName}</div>
        <div className="connector-status-row">{status}</div>
        {pendingTask && (
          <div className="connector-pending">
            <b>Pending:</b> {pendingTask}
          </div>
        )}
        {difficultyPicker && (
          <div className="connector-difficulty">
            <span className="muted">Project difficulty</span>
            <div className="connector-difficulty-options">
              {(Object.keys(DIFFICULTY_LABELS) as ProjectDifficultyLevel[]).map((level) => (
                <button
                  key={level}
                  type="button"
                  className={`connector-difficulty-btn${difficultyPicker.value === level ? " active" : ""}`}
                  onClick={() => {
                    difficultyPicker.onChange(level);
                    setOpen(false);
                  }}
                >
                  {DIFFICULTY_LABELS[level]}
                </button>
              ))}
            </div>
          </div>
        )}
        {!!quickActions?.length && (
          <div className="connector-quick-actions">
            {quickActions.map((action) => (
              <button
                key={action.value}
                type="button"
                className="connector-quick-btn"
                onClick={() => {
                  onQuickAction?.(action.value);
                  setOpen(false);
                }}
              >
                <strong>{action.label}</strong>
                {action.description && <span>{action.description}</span>}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
