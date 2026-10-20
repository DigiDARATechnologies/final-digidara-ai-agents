import { useEffect, useState } from "react";
import { LEVEL_LABELS, createCareerPlan, fetchCareerPlan, type CareerPlan } from "../lib/learnerApi";

interface Props {
  onToast: (message: string) => void;
}

/** The AI career coach: a week-by-week plan built from every agent over A2A. */
export default function CareerPlanPanel({ onToast }: Props) {
  const [plan, setPlan] = useState<CareerPlan | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    fetchCareerPlan().then((r) => active && setPlan(r.plan)).catch(() => undefined);
    return () => { active = false; };
  }, []);

  async function create() {
    setBusy(true);
    try {
      setPlan((await createCareerPlan("en")).plan);
      onToast("Your plan is ready.");
    } catch (err) {
      onToast((err as Error).message);
    } finally {
      setBusy(false);
    }
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
          <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={() => void create()}>
            {busy ? "Planning…" : plan ? "New plan" : "Create my plan"}
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
