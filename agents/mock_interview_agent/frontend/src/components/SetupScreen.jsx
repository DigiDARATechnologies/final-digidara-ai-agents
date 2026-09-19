import React, { useEffect, useState } from "react";
import { getDailyUsage, startInterview } from "../api";
import {
  APP_ICONS,
  DIFFICULTY_ICONS,
  ROUND_TYPE_ICONS,
} from "../utils/icons";
import PageHeader from "./ui/PageHeader";
import SectionCard from "./ui/SectionCard";
import { reportClientError } from "../utils/clientLogger";

const ROUND_TYPES = [
  {
    key: "technical",
    title: "Technical Interview",
    icon: ROUND_TYPE_ICONS.technical,
    accent: "#4f46e5",
    text: "Concept questions for your selected subject.",
  },
  {
    key: "hr",
    title: "HR Interview",
    icon: ROUND_TYPE_ICONS.hr,
    accent: "#0f9f96",
    text: "Communication, motivation, and workplace readiness.",
  },
];
const DIFFICULTIES = ["Beginner", "Intermediate", "Advanced"];
const DIFFICULTY_ACCENTS = {
  Beginner: "#10b981",
  Intermediate: "#f59e0b",
  Advanced: "#f97360",
};
const QUESTION_ACCENTS = {
  10: "#0f9f96",
};
const QUESTION_COUNTS = [10];
const ROLE_PRESETS = [
  "Python Fullstack Developer",
  "Data Analyst",
  "Digital Marketing Executive",
  "AI Engineer",
];
const StartIcon = APP_ICONS.start;
const SelectedIcon = APP_ICONS.selected;
const DIFFICULTY_DESCRIPTIONS = {
  Beginner: "Simple fundamentals and common questions.",
  Intermediate: "Practical scenarios and usage reasoning.",
  Advanced: "Trade-offs, design, and deeper judgment.",
};

function SelectionIndicator() {
  return (
    <span className="option-selected" aria-hidden="true">
      <SelectedIcon size={14} strokeWidth={2.5} />
    </span>
  );
}

function DifficultyOption({ name, selected, onSelect }) {
  const DifficultyIcon = DIFFICULTY_ICONS[name];

  return (
    <button
      type="button"
      className={`option-card ${selected ? "option-card-active" : ""}`}
      style={{ "--option-accent": DIFFICULTY_ACCENTS[name] }}
      onClick={onSelect}
      aria-pressed={selected}
    >
      <span className="option-icon" aria-hidden="true">
        <DifficultyIcon size={22} strokeWidth={2} />
      </span>
      <strong>{name}</strong>
      <span>{DIFFICULTY_DESCRIPTIONS[name]}</span>
      {selected && <SelectionIndicator />}
    </button>
  );
}

/**
 * Interview setup form for round type, subject, and difficulty.
 * @param {{ studentId: number, onStarted: (id: number, question: string) => void }} props
 */
export default function SetupScreen({ studentId, onStarted }) {
  const [roundType, setRoundType] = useState("technical");
  const [interviewMode, setInterviewMode] = useState("role");
  const [customTopic, setCustomTopic] = useState("");
  const [roleName, setRoleName] = useState(ROLE_PRESETS[0]);
  const [difficulty, setDifficulty] = useState("Beginner");
  const [numQuestions] = useState(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [dailyUsage, setDailyUsage] = useState(null);
  const [quotaLoading, setQuotaLoading] = useState(true);
  const [quotaError, setQuotaError] = useState(null);
  const selectedTechnicalSubject = customTopic.trim();
  const dailyLimitEnabled = dailyUsage?.daily_limit_enabled !== false;
  const remainingToday = dailyUsage?.daily_remaining;
  const effectiveQuestionCount =
    typeof remainingToday === "number"
      ? Math.min(numQuestions, remainingToday)
      : numQuestions;
  const dailyLimitReached = remainingToday === 0;
  const quotaAdjusted =
    typeof remainingToday === "number"
    && remainingToday > 0
    && remainingToday < numQuestions;
  const SummaryRoundIcon = ROUND_TYPE_ICONS[roundType];
  const SummaryFocusIcon = roundType === "hr"
    ? ROUND_TYPE_ICONS.hr
    : APP_ICONS.questions;
  const SummaryDifficultyIcon = DIFFICULTY_ICONS[difficulty];
  const SummaryQuestionsIcon = APP_ICONS.questions;

  useEffect(() => {
    let active = true;

    async function loadDailyUsage() {
      await Promise.resolve();
      if (!active) return;
      setQuotaLoading(true);
      setQuotaError(null);
      try {
        const usage = await getDailyUsage(studentId);
        if (active) setDailyUsage(usage);
      } catch (requestError) {
        reportClientError("daily_usage_load_failed", requestError, {
          student_id: studentId,
        });
        // Starting remains available: the backend performs the authoritative
        // quota check even if this preflight status cannot be loaded.
        if (active) {
          setQuotaError(
            "Today's practice quota could not be loaded. It will be checked again when you start."
          );
        }
      } finally {
        if (active) setQuotaLoading(false);
      }
    }

    loadDailyUsage();
    return () => {
      active = false;
    };
  }, [studentId]);

  async function handleStart() {
    if (roundType === "technical" && interviewMode === "role" && !roleName.trim()) {
      setError("Please select or enter the role you want to practice for.");
      return;
    }
    if (roundType === "technical" && interviewMode === "custom_topic" && !selectedTechnicalSubject) {
      setError("Please enter a custom technical topic.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await startInterview({
        student_id: studentId,
        interview_mode: roundType === "hr" ? "course" : interviewMode,
        round_type: roundType,
        role_name: roundType === "technical" && interviewMode === "role" ? roleName.trim() : null,
        subject: roundType === "technical" && interviewMode === "custom_topic"
          ? selectedTechnicalSubject : null,
        difficulty: difficulty.toLowerCase(),
        num_questions: numQuestions,
      });
      if (res.interview_id) {
        setDailyUsage((current) => ({
          ...(current || {}),
          daily_limit: res.daily_limit,
          daily_limit_enabled: res.daily_limit_enabled,
          daily_answered_count: res.daily_answered_count,
          daily_remaining: res.daily_remaining,
        }));
        onStarted(res.interview_id, res.question, {
          totalQuestions: res.total_questions,
          difficulty: res.difficulty || difficulty.toLowerCase(),
          questionOrder: res.question_order || 1,
          realQuestionIndex: res.real_question_index || 1,
          isFrequentlyAsked: Boolean(res.is_frequently_asked),
          resumedExisting: Boolean(res.resumed_existing),
        });
      } else {
        if (typeof res.daily_remaining === "number") {
          setDailyUsage(res);
        }
        setError(res.error || "Could not start the interview. Check the backend server.");
      }
    } catch (e) {
      reportClientError("interview_start_failed", e, {
        student_id: studentId,
        round_type: roundType,
      });
      setError(e.message || "Could not reach the interview service.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page setup-page">
      <PageHeader
        eyebrow="New session"
        title="New Mock Interview"
        description="Configure a conversational interview and start when you are ready."
      />

      <ol className="setup-steps" aria-label="Interview setup sections">
        {["Interview type", "Details", "Questions", "Review"].map((label, index) => (
          <li key={label}>
            <span>{index + 1}</span>
            <strong>{label}</strong>
          </li>
        ))}
      </ol>

      <div className="setup-layout">
        <div className="setup-main">
          <SectionCard className="setup-section round-type-section" title="Round Type" subtitle="Choose the interview style.">
            <div className="option-card-grid two-col">
              {ROUND_TYPES.map(({ key, title, icon: IconComponent, accent, text }) => (
                <button
                  key={key}
                  type="button"
                  className={`option-card ${roundType === key ? "option-card-active" : ""}`}
                  style={{ "--option-accent": accent }}
                  onClick={() => { setRoundType(key); setError(null); }}
                  aria-pressed={roundType === key}
                >
                  <span className="option-icon" aria-hidden="true">
                    <IconComponent size={22} strokeWidth={2} />
                  </span>
                  <strong>{title}</strong>
                  <span>{text}</span>
                  {roundType === key && <SelectionIndicator />}
                </button>
              ))}
            </div>
          </SectionCard>

          {roundType === "technical" && (
            <>
              <SectionCard className="setup-section" title="Technical Interview Type" subtitle="Choose how you want to practice technical interview questions.">
                <div className="option-card-grid two-col">
                  {[
                    ["role", "Role-Based", "Practice the stack used for a real job role."],
                    ["custom_topic", "Custom Topics", "Practice any technical topic you enter."],
                  ].map(([key, title, description]) => (
                    <button key={key} type="button" className={`option-card ${interviewMode === key ? "option-card-active" : ""}`} onClick={() => { setInterviewMode(key); setError(null); }} aria-pressed={interviewMode === key}>
                      <strong>{title}</strong><span>{description}</span>{interviewMode === key && <SelectionIndicator />}
                    </button>
                  ))}
                </div>
              </SectionCard>

              {interviewMode === "role" && (
                <SectionCard className="setup-section" title="Role-Based Interview" subtitle="Choose a preset role or enter any role. We will cover its relevant stack.">
                  <div className="option-card-grid subjects-grid">
                    {ROLE_PRESETS.map((role) => <button key={role} type="button" className={`option-card compact ${roleName === role ? "option-card-active" : ""}`} onClick={() => { setRoleName(role); setError(null); }} aria-pressed={roleName === role}><strong>{role}</strong>{roleName === role && <SelectionIndicator />}</button>)}
                  </div>
                  <div className="custom-topic-field"><label htmlFor="custom-role-name">Custom role</label><input id="custom-role-name" value={roleName} onChange={(event) => { setRoleName(event.target.value); setError(null); }} placeholder="e.g. DevOps Engineer" maxLength={150} /><span>Custom roles are mapped to realistic interview subjects before the session starts.</span></div>
                </SectionCard>
              )}

              {interviewMode === "custom_topic" && (
                <SectionCard className="setup-section" title="Custom Topics Interview" subtitle="Enter any technical topic you want to practice.">
                  <div className="custom-topic-field"><label htmlFor="standalone-custom-topic">Technical topic</label><input id="standalone-custom-topic" value={customTopic} onChange={(event) => { setCustomTopic(event.target.value); setError(null); }} placeholder="e.g. Kubernetes, React Hooks, System Design" maxLength={150} /><span>Uses the existing dynamic custom-topic question path.</span></div>
                </SectionCard>
              )}
            </>
          )}

          <SectionCard className="setup-section difficulty-section" title="Difficulty" subtitle="Calibrate the interview depth.">
            <div className="option-card-grid three-col">
              {DIFFICULTIES.map((d) => (
                <DifficultyOption
                  key={d}
                  name={d}
                  selected={difficulty === d}
                  onSelect={() => setDifficulty(d)}
                />
              ))}
            </div>
          </SectionCard>

          <SectionCard className="setup-section questions-section" title="Number of Questions" subtitle="Each interview contains 10 questions.">
            <div className="option-card-grid">
              {QUESTION_COUNTS.map((count) => (
                <button
                  key={count}
                  type="button"
                  className="option-card option-card-active"
                  style={{ "--option-accent": QUESTION_ACCENTS[count] }}
                  aria-pressed="true"
                  disabled
                >
                  <span className="option-icon">{count}</span>
                  <strong>{count} Questions</strong>
                  <span>A complete interview practice session.</span>
                  <SelectionIndicator />
                </button>
              ))}
            </div>
            {(quotaLoading || dailyLimitEnabled) && (
              <div
                className={`quota-status ${dailyLimitReached ? "quota-status-limit" : ""}`}
                aria-live="polite"
              >
                {quotaLoading && <span>Checking today&apos;s remaining practice quota…</span>}
                {!quotaLoading && dailyLimitReached && (
                  <strong>
                    You&apos;ve reached today&apos;s practice limit (10 questions).
                    Please come back tomorrow to continue practicing.
                  </strong>
                )}
                {!quotaLoading && !dailyLimitReached && typeof remainingToday === "number" && (
                  <span>
                    {remainingToday} of 10 answered questions remaining today.
                    {quotaAdjusted && (
                      <> This interview will be reduced to {remainingToday} questions.</>
                    )}
                  </span>
                )}
              </div>
            )}
            {quotaError && <p className="error-text" role="alert">{quotaError}</p>}
          </SectionCard>
        </div>

        <aside className="summary-panel">
          <p className="eyebrow">Interview Summary</p>
          <h3>Ready when you are</h3>
          <div className="summary-list">
            <div>
              <span className="summary-label">
                <span className="summary-row-icon" style={{ "--summary-accent": "#4f46e5" }} aria-hidden="true">
                  <SummaryRoundIcon size={16} strokeWidth={2} />
                </span>
                Round
              </span>
              <strong>{roundType === "technical" ? "Technical Interview" : "HR Interview"}</strong>
            </div>
            <div>
              <span className="summary-label">
                <span className="summary-row-icon" style={{ "--summary-accent": roundType === "hr" ? "#0f9f96" : "#4f46e5" }} aria-hidden="true">
                  <SummaryFocusIcon size={16} />
                </span>
                Subject
              </span>
              <strong>
                {roundType === "hr"
                  ? "HR"
                  : interviewMode === "role"
                    ? roleName || "Enter a role"
                    : selectedTechnicalSubject || "Enter a custom topic"}
              </strong>
            </div>
            <div>
              <span className="summary-label">
                <span className="summary-row-icon" style={{ "--summary-accent": DIFFICULTY_ACCENTS[difficulty] }} aria-hidden="true">
                  <SummaryDifficultyIcon size={16} strokeWidth={2} />
                </span>
                Difficulty
              </span>
              <strong>{difficulty}</strong>
            </div>
            <div>
              <span className="summary-label">
                <span className="summary-row-icon" style={{ "--summary-accent": QUESTION_ACCENTS[numQuestions] }} aria-hidden="true">
                  <SummaryQuestionsIcon size={16} strokeWidth={2} />
                </span>
                Questions
              </span>
              <strong>
                {quotaAdjusted
                  ? `${effectiveQuestionCount} (daily quota)`
                  : numQuestions}
              </strong>
            </div>
          </div>
          {error && <p className="error-text" role="alert">{error}</p>}
          <button
            className="primary-btn"
            onClick={handleStart}
            disabled={loading || dailyLimitReached}
          >
            {loading ? (
              <span className="button-spinner" aria-hidden="true" />
            ) : (
              <StartIcon className="button-icon" size={18} strokeWidth={2} />
            )}
            {loading ? "Starting..." : "Start Interview"}
          </button>
        </aside>
      </div>
    </div>
  );
}
