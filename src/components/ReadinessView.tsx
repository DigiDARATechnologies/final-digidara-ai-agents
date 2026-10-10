import { useCallback, useEffect, useState } from "react";
import CareerPlanPanel from "./CareerPlanPanel";
import LearnerProfileForm, { type ProfileInput } from "./LearnerProfileForm";
import MemoryPanel from "./MemoryPanel";
import {
  LEVEL_IDS,
  BAND_TONE,
  LEVEL_LABELS,
  fetchReadiness,
  fetchReadinessHistory,
  saveLearnerProfile,
  setMyLevel,
  setProgressSharing,
  type AgentLevel,
  type Band,
  type LearnerSummary,
  type LevelId,
  type Readiness,
  type ReadinessArea,
} from "../lib/learnerApi";

interface Props {
  summary: LearnerSummary;
  onSummaryChange: (summary: LearnerSummary) => void;
  onBack: () => void;
  onToast: (message: string) => void;
}

function when(iso: string | null | undefined) {
  if (!iso) return "";
  const date = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`);
  return date.toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

export function ScoreRing({ score, band, size = 148 }: { score: number | null; band: Band; size?: number }) {
  const radius = size / 2 - 10;
  const circumference = 2 * Math.PI * radius;
  const value = score ?? 0;
  return (
    <svg className={`rd-ring tone-${BAND_TONE[band]}`} width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img"
      aria-label={score === null ? "Not started" : `Job readiness ${score} out of 100`}>
      <circle cx={size / 2} cy={size / 2} r={radius} className="rd-ring-track" />
      <circle cx={size / 2} cy={size / 2} r={radius} className="rd-ring-value"
        strokeDasharray={`${(value / 100) * circumference} ${circumference}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" className="rd-ring-text">
        {score === null ? "–" : Math.round(score)}
      </text>
    </svg>
  );
}

/** How each area's score is worked out, in the learner's words. */
const AREA_EXPLANATION: Record<string, string> = {
  codeforge_agent: "Your best score on every problem you tried (Medium counts 2×, Hard 3×), scaled by how many you've solved: half credit at your first solve, full credit at 20 solved.",
  mock_interview_agent: "The average overall score of your last 5 completed interviews (out of 10, shown out of 100).",
  aptitude_agent: "The average percentage of your last 10 completed aptitude tests.",
  communication_agent: "The average of your writing, speaking and pronunciation scores from your latest sessions.",
  resume_builder_agent: "Your best ATS score across your resumes. Run an ATS check to get one.",
  capstone_project_agent: "Your best graded capstone project score.",
  certificate_agent: "Your best exam score in each certification topic, averaged.",
};

const METRIC_LABELS: Record<string, string> = {
  problems_solved: "solved", problems_attempted: "attempted", hard_solved: "hard solved", medium_solved: "medium solved",
  interviews_completed: "interviews", tests_completed: "tests", best_percentage: "best %", resumes: "resumes",
  ats_checks: "ATS checks", certificates: "certificates", graded: "graded", writing_score: "writing",
  speaking_score: "speaking", pronunciation_score: "pronunciation",
};

// METRIC_LABELS order, not the stored key order (MySQL JSON reorders keys).
const METRIC_ORDER = ["problems_solved", "problems_attempted", "medium_solved", "hard_solved", ...Object.keys(METRIC_LABELS)];

function metricLine(metrics: ReadinessArea["metrics"]): string {
  return [...new Set(METRIC_ORDER)]
    .filter((key) => key in metrics && METRIC_LABELS[key] && metrics[key] !== null && metrics[key] !== undefined && metrics[key] !== false)
    .slice(0, 3)
    .map((key) => `${typeof metrics[key] === "number" ? Math.round(metrics[key] as number) : metrics[key]} ${METRIC_LABELS[key]}`)
    .join(" · ");
}

const LEVEL_DIFFICULTY: Record<LevelId, string> = { beginner: "Easy", medium: "Medium", hard: "Hard", professional: "Hard" };

function LevelPicker({ value, onChange, disabled, upLocked }: {
  value: LevelId; onChange: (level: LevelId) => void; disabled?: boolean; upLocked?: boolean;
}) {
  const current = LEVEL_IDS.indexOf(value);
  return (
    <div className="rd-levels" role="radiogroup" aria-label="Level">
      {LEVEL_IDS.map((level, index) => {
        const locked = Boolean(upLocked) && index > current;
        return (
          <button key={level} type="button" role="radio" aria-checked={value === level} disabled={disabled || locked}
            title={locked ? `Complete 50% of ${LEVEL_LABELS[value]} to unlock` : undefined}
            className={`rd-level lv-${level}${value === level ? " active" : ""}${locked ? " locked" : ""}`}
            onClick={() => value !== level && onChange(level)}>
            {locked ? "🔒 " : ""}{LEVEL_LABELS[level]}
          </button>
        );
      })}
    </div>
  );
}

/** "Beginner progress 29% · Easy problems solved" with what it unlocks. */
function LevelProgress({ area }: { area: ReadinessArea }) {
  const progress = area.level_progress;
  if (area.status !== "assessed" || progress === null || progress === undefined) return null;
  const what = area.level_progress_basis === "level" && area.agent_name === "codeforge_agent"
    ? `of ${LEVEL_DIFFICULTY[area.level]} problems solved` : "your score at this level";
  const next = area.next_level ? LEVEL_LABELS[area.next_level] : null;
  return (
    <div className="rd-progress">
      <div className="rd-progress-head">
        <span>{LEVEL_LABELS[area.level]} progress</span><b>{Math.round(progress)}%</b>
      </div>
      <div className="rd-bar thin"><span style={{ width: `${Math.min(100, progress)}%` }} /></div>
      <p className="rd-muted">
        {Math.round(progress)}% {what}.{" "}
        {next ? (area.can_level_up ? `${next} is unlocked; at 100% you move up automatically.` : `50% unlocks ${next}; 100% moves you up automatically.`)
          : "This is the top level."}
      </p>
    </div>
  );
}

function AreaCard({ area, onLevel, busy }: { area: ReadinessArea; onLevel: (level: LevelId) => void; busy: boolean }) {
  const scored = area.status === "assessed" && area.score !== null;
  return (
    <div className={`rd-area status-${area.status}`}>
      <div className="rd-area-head">
        <div>
          <h3>{area.label}</h3>
          <span className="rd-weight">{area.weight}% of readiness</span>
        </div>
        <div className="rd-area-score">
          {scored ? <><b>{Math.round(area.score as number)}</b><span>/100</span></> : <span className="rd-muted">
            {area.status === "unavailable" ? "Unavailable" : "Not started"}</span>}
        </div>
      </div>
      <div className="rd-bar"><span style={{ width: `${scored ? area.score : 0}%` }} /></div>
      {metricLine(area.metrics) && <p className="rd-metrics">{metricLine(area.metrics)}</p>}
      {area.promoted_from && (
        <p className="rd-promoted">🎉 You completed {LEVEL_LABELS[area.promoted_from]} and moved up to {LEVEL_LABELS[area.level]}.</p>
      )}
      <LevelPicker value={area.level} onChange={onLevel} disabled={busy} upLocked={!area.can_level_up} />
      <LevelProgress area={area} />
      {area.suggested_level && area.suggested_level !== area.level && (
        <button type="button" className="rd-suggest" disabled={busy} onClick={() => onLevel(area.suggested_level as LevelId)}>
          <b>{LEVEL_LABELS[area.suggested_level]}</b> is unlocked — switch
        </button>
      )}
      {(area.strengths.length > 0 || area.gaps.length > 0) && (
        <div className="rd-notes">
          {area.strengths.length > 0 && <ul className="rd-good">{area.strengths.map((s) => <li key={s}>{s}</li>)}</ul>}
          {area.gaps.length > 0 && <ul className="rd-gap">{area.gaps.map((g) => <li key={g}>{g}</li>)}</ul>}
        </div>
      )}
      {area.status === "unavailable" && area.reason && <p className="rd-muted rd-reason">{area.reason}</p>}
      {AREA_EXPLANATION[area.agent_name] && (
        <details className="rd-how">
          <summary>How this score works</summary>
          <p>{AREA_EXPLANATION[area.agent_name]} Levels: complete 50% of your level to unlock the next one; at 100% you move up automatically.</p>
        </details>
      )}
    </div>
  );
}

function Trend({ points }: { points: { overall: number | null; computed_at: string }[] }) {
  // Only checks that produced a score: "not started" is not a 0 on the chart.
  const values = points.filter((p) => p.overall !== null).map((p) => p.overall as number);
  if (values.length < 2) return <p className="rd-muted">Your trend appears once your readiness has been scored a few times.</p>;
  const width = 320;
  const height = 70;
  const step = width / (values.length - 1);
  const path = values.map((v, i) => `${i === 0 ? "M" : "L"}${(i * step).toFixed(1)},${(height - (v / 100) * height).toFixed(1)}`).join(" ");
  const first = values[0];
  const last = values[values.length - 1];
  return (
    <div className="rd-trend">
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label={`Readiness went from ${first} to ${last}`}>
        <path d={path} />
      </svg>
      <span className={last >= first ? "up" : "down"}>{first.toFixed(0)} → {last.toFixed(0)}</span>
    </div>
  );
}

export default function ReadinessView({ summary, onSummaryChange, onBack, onToast }: Props) {
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [history, setHistory] = useState<{ overall: number | null; band: Band; computed_at: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyAgent, setBusyAgent] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async (refresh: boolean) => {
    setLoading(true);
    setError("");
    try {
      const [result, trend] = await Promise.all([fetchReadiness(refresh), fetchReadinessHistory().catch(() => [])]);
      setReadiness(result);
      setHistory(trend);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Always fresh on open: the server reuses a result from the last few seconds.
  useEffect(() => { void load(true); }, [load]);

  async function changeLevel(agentName: string, level: LevelId) {
    setBusyAgent(agentName);
    try {
      const updated = await setMyLevel(agentName, level);
      onSummaryChange({ ...summary, levels: summary.levels.map((l) => (l.agent_name === agentName ? updated : l)) });
      setReadiness((r) => r && { ...r, areas: r.areas.map((a) => (a.agent_name === agentName ? { ...a, level, promoted_from: undefined } : a)) });
      // Progress is per level: measure it again at the new one.
      void load(true);
      onToast(`${updated.agent_label} is now ${LEVEL_LABELS[level]}.`);
    } catch (err) {
      onToast((err as Error).message);
    } finally {
      setBusyAgent(null);
    }
  }

  async function saveProfile(profile: ProfileInput) {
    setSaving(true);
    try {
      onSummaryChange(await saveLearnerProfile(profile));
      setEditing(false);
      onToast("Profile saved. Every agent will use it from your next session.");
    } catch (err) {
      onToast((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function toggleSharing(share: boolean) {
    try {
      const membership = await setProgressSharing(share);
      onSummaryChange({ ...summary, membership });
    } catch (err) {
      onToast((err as Error).message);
    }
  }

  const profile = summary.profile;
  const scoredAgents = new Set(readiness?.areas.map((a) => a.agent_name) ?? []);
  const otherLevels: AgentLevel[] = summary.levels.filter((l) => !scoredAgents.has(l.agent_name));
  const membership = summary.membership;

  return (
    <div className="pv-page rd-page">
      <div className="pv-inner">
        <button className="hp-back" onClick={onBack}>← Back</button>

        <section className="rd-hero">
          {readiness ? <ScoreRing score={readiness.overall} band={readiness.band} /> : <div className="rd-ring-placeholder" />}
          <div className="rd-hero-text">
            <span className="rd-kicker">Job readiness{profile.target_role ? ` · ${profile.target_role}` : ""}</span>
            <h1>{readiness ? readiness.band_label : loading ? "Checking every agent…" : "Job readiness"}</h1>
            {readiness && (
              <p className="rd-muted">
                {readiness.coverage.assessed} of {readiness.coverage.total} areas assessed · checked {when(readiness.computed_at)}
              </p>
            )}
            {readiness && (
              <details className="rd-how">
                <summary>How is this calculated?</summary>
                <p>
                  Each area's score (0–100) counts by its weight: Coding 25%, Interview 20%, Aptitude 15%, Communication 15%,
                  Resume 10%, Projects 10%, Certification 5%. Areas you haven't started yet count as 0, because an untested
                  skill isn't job-ready yet.{" "}
                  {readiness.overall !== null && `Yours: ${readiness.areas.filter((a) => a.status === "assessed" && a.score !== null)
                    .map((a) => `${a.label} ${Math.round(a.score as number)} × ${a.weight}%`).join(" + ")} = ${Math.round(readiness.overall)}.`}
                </p>
              </details>
            )}
            <div className="rd-hero-actions">
              <button className="btn btn-primary btn-sm" disabled={loading} onClick={() => void load(true)}>
                {loading ? "Checking…" : "Check again"}
              </button>
              <button className="btn btn-outline btn-sm" onClick={() => setEditing(true)}>Edit profile</button>
            </div>
          </div>
        </section>

        {error && <p className="form-error" role="alert">{error}</p>}

        <CareerPlanPanel onToast={onToast} />

        {readiness && readiness.next_steps.length > 0 && (
          <section className="pv-section">
            <h2>Do this next</h2>
            <ol className="rd-steps">{readiness.next_steps.map((step) => <li key={step}>{step}</li>)}</ol>
          </section>
        )}

        {readiness && (
          <section className="pv-section">
            <div className="pv-section-head">
              <h2>Areas and levels</h2>
              <span className="rd-muted">Every agent starts at Beginner. Choose a level, or take the suggestion.</span>
            </div>
            <div className="rd-grid">
              {readiness.areas.map((area) => (
                <AreaCard key={area.agent_name} area={area} busy={busyAgent === area.agent_name}
                  onLevel={(level) => void changeLevel(area.agent_name, level)} />
              ))}
            </div>
            {otherLevels.length > 0 && (
              <div className="rd-other-levels">
                {otherLevels.map((level) => (
                  <div key={level.agent_name} className="rd-other-row">
                    <span>{level.agent_label}</span>
                    <LevelPicker value={level.level} disabled={busyAgent === level.agent_name}
                      onChange={(next) => void changeLevel(level.agent_name, next)} />
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        <section className="pv-section rd-two">
          <div className="rd-panel">
            <h2>Trend</h2>
            <Trend points={history} />
          </div>
          <div className="rd-panel">
            <h2>Your profile</h2>
            <dl className="rd-profile">
              <dt>Target role</dt><dd>{profile.target_role || "—"}</dd>
              <dt>Degree</dt><dd>{profile.degree || "—"}</dd>
              <dt>Experience</dt><dd>{profile.experience === "experienced" ? "Experienced" : "Fresher / student"}</dd>
            </dl>
            <div className="rd-chips">{profile.skills.map((skill) => <span key={skill} className="lp-chip">{skill}</span>)}</div>
          </div>
        </section>

        <MemoryPanel onToast={onToast}
          agentLabels={Object.fromEntries(summary.levels.map((level) => [level.agent_name, level.agent_label]))} />

        {membership && (
          <section className="pv-section rd-panel">
            <h2>{membership.organization.name}</h2>
            <label className="lp-check">
              <input type="checkbox" checked={membership.progress_shared} onChange={(e) => void toggleSharing(e.target.checked)} />
              <span>Let {membership.organization.name} see my job readiness and levels.</span>
            </label>
          </section>
        )}
      </div>

      {editing && (
        <div className="modal-overlay open" onClick={(e) => e.target === e.currentTarget && setEditing(false)}>
          <div className="modal rd-modal" role="dialog" aria-modal="true" aria-label="Edit profile">
            <div className="rd-modal-head">
              <h2>Edit profile</h2>
              <button type="button" className="link-btn" onClick={() => setEditing(false)}>Close</button>
            </div>
            <LearnerProfileForm initial={profile} submitLabel="Save profile" busy={saving} onSubmit={(p) => void saveProfile(p)} />
          </div>
        </div>
      )}
    </div>
  );
}
