import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { AptitudeFlowState } from "../lib/aptitudeFlow";
import { getMixedTestConfig, saveMixedTestConfig, type MixedTestCategory, type MixedTestConfig } from "../lib/aptitudeApi";

const CATEGORY_DETAILS: Record<string, string> = {
  "Quantitative Aptitude": "Numerical and mathematical problem-solving.",
  "Logical Reasoning": "Pattern recognition and logical deduction.",
  "Verbal Ability": "Language, comprehension, and grammar skills.",
  "Analytical Reasoning": "Structured problem-solving and reasoning puzzles.",
  "Computer Fundamentals": "Core computer science concepts.",
  "Technical Aptitude": "Programming logic and technical problem-solving.",
};

const CATEGORY_ICONS: Record<string, string> = {
  "Quantitative Aptitude": "🔢", "Logical Reasoning": "🧩", "Verbal Ability": "📖",
  "Analytical Reasoning": "💡", "Computer Fundamentals": "🖥️", "Technical Aptitude": "</>",
};

function OverviewStat({ label, value }: { label: string; value: string }) {
  return <div className="aptitude-overview-stat"><span>{label}</span><strong>{value}</strong></div>;
}

function Timer({ seconds, total }: { seconds: number; total: number }) {
  const minutes = Math.floor(Math.max(0, seconds) / 60);
  const remaining = Math.max(0, seconds) % 60;
  const progress = total > 0 ? Math.max(0, Math.min(100, seconds / total * 100)) : 0;
  return <div className={`aptitude-countdown${seconds <= 10 ? " urgent" : ""}`} role="timer" aria-live={seconds <= 10 ? "polite" : "off"} aria-label={`${seconds} seconds remaining`}><span>⏱</span><strong>{minutes}:{String(remaining).padStart(2, "0")}</strong><small>{seconds > 0 ? "remaining" : "time expired"}</small><i aria-hidden="true"><b style={{ width: `${progress}%` }} /></i></div>;
}

function ExitTestControl({ onExit, pending = false }: { onExit: () => void; pending?: boolean }) {
  const [confirming, setConfirming] = useState(false);
  const cancelRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!confirming) return;
    cancelRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") setConfirming(false); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [confirming]);
  return <>
    <button type="button" className="aptitude-exit-trigger" onClick={() => setConfirming(true)} disabled={pending}>Exit Test</button>
    {confirming && <div className="aptitude-exit-backdrop"><div className="aptitude-exit-dialog" role="alertdialog" aria-modal="true" aria-labelledby="aptitude-exit-title" aria-describedby="aptitude-exit-description">
      <h2 id="aptitude-exit-title">Exit Test?</h2>
      <p id="aptitude-exit-description">Are you sure you want to exit this test? Your current test attempt will be ended and you cannot continue it.</p>
      <div className="aptitude-exit-dialog-actions"><button type="button" ref={cancelRef} onClick={() => setConfirming(false)}>Cancel</button><button type="button" className="aptitude-exit-confirm" disabled={pending} onClick={() => { setConfirming(false); onExit(); }}>Exit Test</button></div>
    </div></div>}
  </>;
}

export default function AptitudePracticePanel({ state, onChoose, onExpire, hintPending = false, exitPending = false }: { state: AptitudeFlowState; onChoose: (value: string) => void; onExpire: () => void; hintPending?: boolean; exitPending?: boolean }) {
  const [config, setConfig] = useState<MixedTestConfig | null>(null);
  const [draft, setDraft] = useState<MixedTestCategory[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [seconds, setSeconds] = useState(0);
  const expiredQuestionRef = useRef("");
  const deadlineRef = useRef({ questionKey: "", at: Number.POSITIVE_INFINITY });
  const questionKey = `${state.testId || ""}`;

  useEffect(() => {
    if (state.mode !== "mixed" || !state.sessionToken || state.step !== "awaiting_language") return;
    let active = true;
    setLoading(true);
    getMixedTestConfig(state.sessionToken)
      .then((result) => { if (active) { setConfig(result); setDraft(result.categories); setError(""); } })
      .catch((requestError) => { if (active) setError((requestError as Error).message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [state.mode, state.sessionToken, state.step]);

  useLayoutEffect(() => {
    const remaining = Number(state.question?.overall_remaining_seconds ?? state.question?.remaining_seconds ?? state.question?.allowed_time_seconds ?? 0);
    const deadline = Number(state.question?.deadline_at_ms || Date.now() + remaining * 1000);
    // Record the deadline synchronously before the expiry effect runs. A new
    // Timer component begins with seconds=0, which must not be mistaken for
    // an expired question before its first countdown update is committed.
    deadlineRef.current = { questionKey, at: deadline };
    const update = () => setSeconds(Math.max(0, Math.ceil((deadline - Date.now()) / 1000)));
    update();
    if (state.step !== "awaiting_question") return;
    const timer = window.setInterval(update, 250);
    return () => window.clearInterval(timer);
  }, [questionKey, state.question?.deadline_at_ms, state.question?.overall_remaining_seconds, state.question?.remaining_seconds, state.step]);

  useEffect(() => {
    const activeDeadline = deadlineRef.current;
    if (state.step !== "awaiting_question" || state.question?.status !== "unanswered" || seconds > 0 || !state.question || activeDeadline.questionKey !== questionKey || Date.now() < activeDeadline.at || expiredQuestionRef.current === questionKey) return;
    expiredQuestionRef.current = questionKey;
    onExpire();
  }, [onExpire, questionKey, seconds, state.question, state.step]);

  const total = useMemo(() => draft.reduce((sum, category) => sum + category.question_count, 0), [draft]);
  const limits = config?.limits;
  const dirty = !!config && JSON.stringify(draft) !== JSON.stringify(config.categories);
  const updateCount = (categoryId: string, direction: number) => {
    if (!limits) return;
    setDraft((items) => items.map((item) => item.category_id === categoryId
      ? { ...item, question_count: Math.max(limits.min_per_category, Math.min(limits.max_per_category, item.question_count + direction)) }
      : item));
  };
  const save = async () => {
    if (!state.sessionToken || !limits || total === 0 || total > limits.max_total) {
      if (total === 0) setError("Select at least one question across the categories.");
      return;
    }
    setSaving(true); setError("");
    try {
      const result = await saveMixedTestConfig(state.sessionToken, draft.map(({ category_id, question_count }) => ({ category_id, question_count })));
      setConfig(result); setDraft(result.categories);
    } catch (requestError) { setError((requestError as Error).message); }
    finally { setSaving(false); }
  };

  if (state.step === "awaiting_question" && state.question && state.tokenInterrupted) {
    return <section className="aptitude-practice-panel aptitude-live-panel" aria-label="Aptitude test paused for token replenishment">
      <div className="aptitude-live-details"><span className="aptitude-panel-eyebrow">TEST PAUSED</span><strong>Question {state.question.sequence} of {state.question.total_questions}</strong><p>Top up your token balance to continue this attempt.</p><ExitTestControl onExit={() => onChoose("exit test")} pending={exitPending} /></div>
      <div className="aptitude-live-actions"><Timer seconds={seconds} total={state.question.total_duration_seconds || state.question.allowed_time_seconds} /><button type="button" className="aptitude-hint-button" onClick={() => onChoose("continue test")}>Continue Test</button></div>
    </section>;
  }

  if (state.step === "awaiting_question" && state.question) {
    const status = state.question.status || "unanswered";
    const nav = state.question.navigation || Array.from({ length: state.question.total_questions }, (_, index) => ({ sequence: index + 1, status: "unanswered" as const, visited: false }));
    return <section className="aptitude-practice-panel aptitude-live-panel aptitude-active-panel" aria-label="Current question status">
      <div className="aptitude-live-heading"><div><span className="aptitude-panel-eyebrow">LIVE PRACTICE</span><strong>Question {state.question.sequence} of {state.question.total_questions}</strong><p>{state.question.category} · {state.question.difficulty}{state.question.topic_is_starred ? " · ★ Priority topic" : ""}</p></div><ExitTestControl onExit={() => onChoose("exit test")} pending={exitPending} /></div>
      <div className="aptitude-live-timer"><Timer seconds={status === "unanswered" ? seconds : 0} total={state.question.total_duration_seconds || state.question.allowed_time_seconds} /></div>
      <div className="aptitude-live-navigation"><div className="aptitude-question-nav" aria-label="Question navigation"><span>Questions</span>{nav.map((item) => <button type="button" key={item.sequence} className={`aptitude-question-number ${item.status}${item.sequence === state.question?.sequence ? " current" : ""}`} aria-label={`Question ${item.sequence} — ${item.sequence === state.question?.sequence ? "Current" : item.status}`} onClick={() => onChoose(`__aptitude_nav:${item.sequence}`)}>{item.sequence}</button>)}</div><small className="aptitude-question-legend">Green = answered · outlined = current · unfilled = unanswered</small></div>
      {state.hintText && <div className="aptitude-hint-text"><b>Hint</b><span>{state.hintText}</span></div>}
      {status === "unanswered" && <div className="aptitude-live-actions"><button type="button" className="aptitude-hint-button" onClick={() => onChoose("skip question")} disabled={seconds <= 0}>Skip Question</button><button type="button" className="aptitude-hint-button" onClick={() => onChoose("hint")} disabled={hintPending || seconds <= 0 || state.hintsRemaining === 0 || !!state.hintText}>{state.hintText ? "Hint shown" : hintPending ? "Generating hint…" : `✦ Get a hint (${state.hintsRemaining ?? state.question.hints_remaining} left)`}</button></div>}
    </section>;
  }

  if (state.step === "awaiting_mode") {
    return <section className="aptitude-practice-panel" aria-label="Choose an aptitude assessment">
      <div className="aptitude-panel-heading"><span className="aptitude-panel-eyebrow">APTITUDE PRACTICE</span><h2>Choose how you want to practice</h2></div>
      <div className="aptitude-mode-grid">
        <button type="button" onClick={() => onChoose("mixed")}><strong>Mixed Test</strong><span>Balanced assessment across all six aptitude categories.</span><small>Easy, Medium &amp; Hard · Timed questions</small></button>
        <button type="button" onClick={() => onChoose("category_practice")}><strong>Category Practice</strong><span>Focused, fixed-level practice for one selected category.</span><small>Priority topics marked with ★</small></button>
      </div>
    </section>;
  }

  if (state.mode === "mixed" && state.step === "awaiting_language") {
    return <section className="aptitude-practice-panel" aria-label="Mixed Test overview and setup">
      <div className="aptitude-panel-heading"><span className="aptitude-panel-eyebrow">MIXED TEST</span><h2>Test overview</h2><p>Build a balanced mix of aptitude topics and fixed difficulty levels, then choose the Technical Aptitude language below.</p></div>
      <div className="aptitude-overview-grid"><OverviewStat label="Categories" value="6 areas" /><OverviewStat label="Questions" value={loading ? "…" : `${total || 0} total`} /><OverviewStat label="Timer" value="60–120 sec" /><OverviewStat label="Difficulty" value="Easy + Medium + Hard" /></div>
      <div className="aptitude-config-heading"><div><h3>Categories covered</h3><p>Set each category independently from 0 to 10 questions. Select at least one question overall.</p></div><b>{total} total</b></div>
      <div className="aptitude-config-grid">
        {draft.map((category) => <div className="aptitude-config-card" key={category.category_id}><span>{CATEGORY_ICONS[category.category_name] || "✦"}</span><div><strong>{category.category_name}</strong><small>{CATEGORY_DETAILS[category.category_name]}</small></div><div className="aptitude-stepper"><button type="button" aria-label={`Remove question from ${category.category_name}`} onClick={() => updateCount(category.category_id, -1)} disabled={saving || !limits || category.question_count <= limits.min_per_category}>−</button><b>{category.question_count}</b><button type="button" aria-label={`Add question to ${category.category_name}`} onClick={() => updateCount(category.category_id, 1)} disabled={saving || !limits || category.question_count >= limits.max_per_category}>+</button></div></div>)}
      </div>
      {error && <p className="aptitude-panel-error" role="alert">{error}</p>}
      <div className="aptitude-panel-actions"><span>{dirty ? "Save your changes before starting." : "Your saved configuration is ready."}</span><button type="button" onClick={save} disabled={!dirty || saving || !!limits && total > limits.max_total}>{saving ? "Saving…" : "Save configuration"}</button></div>
      <div className="aptitude-choice-row"><span>Technical Aptitude language</span>{["Python", "Java", "C", "SQL"].map((language) => <button type="button" key={language} onClick={() => onChoose(language)}>{language}</button>)}</div>
    </section>;
  }

  if (state.step === "awaiting_category") {
    return <section className="aptitude-practice-panel" aria-label="Category Practice overview">
      <div className="aptitude-panel-heading"><span className="aptitude-panel-eyebrow">CATEGORY PRACTICE</span><h2>Choose a category</h2><p>10 focused questions at the level you select. ★ marks a priority topic area.</p></div>
      <div className="aptitude-category-grid">{Object.entries(CATEGORY_DETAILS).map(([category, description]) => <button type="button" key={category} onClick={() => onChoose(category)}><span>{CATEGORY_ICONS[category]}</span><strong>{category}</strong><small>{description}</small><em>★ Priority topics included</em></button>)}</div>
    </section>;
  }

  if (state.step === "awaiting_level") {
    return <section className="aptitude-practice-panel" aria-label="Category Practice level selection">
      <div className="aptitude-panel-heading"><span className="aptitude-panel-eyebrow">{state.category}</span><h2>Choose your level</h2><p>Difficulty stays fixed for all 10 questions. Priority topics will display with ★ during practice.</p></div>
      <div className="aptitude-level-grid">{["Beginner", "Intermediate", "Advanced"].map((level) => <button type="button" key={level} onClick={() => onChoose(level)}><strong>{level}</strong><span>{level === "Beginner" ? "60 seconds per question" : level === "Intermediate" ? "90 seconds per question" : "120 seconds per question"}</span></button>)}</div>
    </section>;
  }

  if (state.step === "awaiting_language") {
    return <section className="aptitude-practice-panel" aria-label="Technical Aptitude language selection"><div className="aptitude-panel-heading"><span className="aptitude-panel-eyebrow">TECHNICAL APTITUDE</span><h2>Choose a programming language</h2><p>Python is the default. Questions and code examples will match your selection.</p></div><div className="aptitude-choice-row">{["Python", "Java", "C", "SQL"].map((language) => <button type="button" key={language} onClick={() => onChoose(language)}>{language}</button>)}</div></section>;
  }

  return null;
}
