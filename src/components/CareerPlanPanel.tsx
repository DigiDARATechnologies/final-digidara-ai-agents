import { useEffect, useState } from "react";
import { LEVEL_LABELS, createCareerPlan, fetchCareerPlan, type CareerPlan } from "../lib/learnerApi";
import { speakNatural, stopSpeaking } from "../lib/voiceEngine";

interface Props {
  onToast: (message: string) => void;
}

function planAsSpeech(plan: CareerPlan): string {
  const weeks = plan.weeks.map((week) => `Week ${week.week}: ${week.focus}. ${week.tasks.map((t) => t.title).join(". ")}.`);
  return [plan.headline, plan.summary, ...weeks, plan.encouragement].filter(Boolean).join(" ");
}

/** The AI career coach: a week-by-week plan built from every agent over A2A. */
export default function CareerPlanPanel({ onToast }: Props) {
  const [plan, setPlan] = useState<CareerPlan | null>(null);
  const [busy, setBusy] = useState<"en" | "ta" | null>(null);
  const [listening, setListening] = useState(false);

  useEffect(() => {
    let active = true;
    fetchCareerPlan().then((r) => active && setPlan(r.plan)).catch(() => undefined);
    return () => { active = false; stopSpeaking(); };
  }, []);

  async function create(language: "en" | "ta") {
    setBusy(language);
    try {
      setPlan((await createCareerPlan(language)).plan);
      onToast(language === "ta" ? "உங்கள் திட்டம் தயார்!" : "Your plan is ready.");
    } catch (err) {
      onToast((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  function listen() {
    if (!plan) return;
    if (listening) {
      stopSpeaking();
      setListening(false);
      return;
    }
    setListening(true);
    void speakNatural(planAsSpeech(plan), { onEnd: () => setListening(false) }, true);
  }

  return (
    <section className="pv-section rd-panel">
      <div className="cp-head">
        <div>
          <span className="rd-kicker">AI career coach</span>
          {plan ? <h3 className="cp-headline">{plan.headline}</h3> : <h3 className="cp-headline">Get a personal plan</h3>}
          <p className="rd-muted">
            {plan ? plan.summary : "Your coach checks every agent, your goal and what your agents remember, then plans your next 4 weeks."}
          </p>
        </div>
        <div className="cp-actions">
          {plan && <button type="button" className="btn btn-outline btn-sm" onClick={listen}>{listening ? "Stop" : "Listen"}</button>}
          <button type="button" className="btn btn-primary btn-sm" disabled={busy !== null} onClick={() => void create("en")}>
            {busy === "en" ? "Planning…" : plan ? "New plan" : "Create my plan"}
          </button>
          <button type="button" className="btn btn-outline btn-sm" disabled={busy !== null} onClick={() => void create("ta")}>
            {busy === "ta" ? "திட்டமிடுகிறது…" : "தமிழில்"}
          </button>
        </div>
      </div>
      {plan && (
        <>
          <div className="cp-weeks">
            {plan.weeks.map((week) => (
              <div key={week.week} className="cp-week">
                <h4>Week {week.week}</h4>
                <h5>{week.focus}</h5>
                {week.tasks.map((task) => (
                  <div key={`${task.agent_name}-${task.title}`} className="cp-task">
                    <b>{task.title}</b>
                    <small><span className={`og-lv lv-${task.level}`}>{LEVEL_LABELS[task.level]}</span>{task.agent_label}{task.why ? ` · ${task.why}` : ""}</small>
                  </div>
                ))}
              </div>
            ))}
          </div>
          {plan.encouragement && <p className="cp-cheer">{plan.encouragement}</p>}
        </>
      )}
    </section>
  );
}
