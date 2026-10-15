import { useCallback, useEffect, useState } from "react";
import CareerPlanPanel from "./CareerPlanPanel";
import LearnerProfileForm, { cleanProfileText, type ProfileInput } from "./LearnerProfileForm";
import MemoryPanel from "./MemoryPanel";
import SkillsInput, { uniqueSkills } from "./SkillsInput";
import { syncJobProfileWithGoal } from "../lib/jobFetchFlow";
import { knownRoleSkills } from "../lib/roleSkills";
import { orgSharingNotice } from "../lib/orgConsent";
import {
  LEVEL_IDS,
  BAND_TONE,
  LEVEL_LABELS,
  fetchReadiness,
  fetchReadinessHistory,
  saveLearnerProfile,
  setMyLevel,
  suggestRoleSkills,
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

/** How each agent measures progress inside a level, in the learner's words. */
const AREA_EXPLANATION: Record<string, string> = {
  codeforge_agent: "the problems you solved at your level's difficulty (Easy for Beginner, then Medium, then Hard), out of every such problem in the technologies you practise.",
  mock_interview_agent: "the average overall score of your last 5 completed interviews (out of 10, shown out of 100).",
  aptitude_agent: "the average percentage of your last 10 completed aptitude tests.",
  communication_agent: "the average of your writing, speaking and pronunciation scores from your latest sessions.",
  resume_builder_agent: "your best ATS score across your resumes. Run an ATS check to get one.",
  capstone_project_agent: "your best graded capstone project score.",
  certificate_agent: "your best exam score in each certification topic, averaged.",
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

/** The four levels. With `gated`, only the next level can be chosen, and only
 * once it is unlocked (50% of the current one); lower levels stay open.
 * `scores` shows each level's own progress under its name. */
function LevelPicker({ value, onChange, disabled, gated, nextUnlocked, scores, unlockAt = 50 }: {
  value: LevelId; onChange: (level: LevelId) => void; disabled?: boolean;
  gated?: boolean; nextUnlocked?: boolean; scores?: Partial<Record<LevelId, number>>; unlockAt?: number;
}) {
  const current = LEVEL_IDS.indexOf(value);
  return (
    <div className="rd-levels" role="radiogroup" aria-label="Level">
      {LEVEL_IDS.map((level, index) => {
        const locked = Boolean(gated) && (index > current + 1 || (index === current + 1 && !nextUnlocked));
        const reason = index > current + 1
          ? `Unlocks after ${LEVEL_LABELS[LEVEL_IDS[index - 1]]}`
          : unlockAt >= 100 ? `Complete all of ${LEVEL_LABELS[value]} to unlock` : `Complete ${unlockAt}% of ${LEVEL_LABELS[value]} to unlock`;
        const score = scores?.[level];
        return (
          <button key={level} type="button" role="radio" aria-checked={value === level} disabled={disabled || locked}
            title={locked ? reason : undefined}
            className={`rd-level lv-${level}${value === level ? " active" : ""}${locked ? " locked" : ""}`}
            onClick={() => value !== level && onChange(level)}>
            {locked ? "🔒 " : ""}{LEVEL_LABELS[level]}
            {score !== undefined && <small className="rd-level-score">{score >= 100 ? "✓ 100%" : `${Math.round(score)}%`}</small>}
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
  const what = area.level_progress_basis !== "level" ? "(this agent uses its overall score for levels)"
    : area.agent_name === "codeforge_agent" ? `of ${LEVEL_DIFFICULTY[area.level]} problems solved`
      : "from your last 5 sessions at this level";
  const next = area.next_level ? LEVEL_LABELS[area.next_level] : null;
  return (
    <div className="rd-progress">
      <div className="rd-progress-head">
        <span>{LEVEL_LABELS[area.level]} progress</span><b>{Math.round(progress)}%</b>
      </div>
      <div className="rd-bar thin"><span style={{ width: `${Math.min(100, progress)}%` }} /></div>
      <p className="rd-muted">
        {Math.round(progress)}% {what}.{" "}
        {next ? (area.can_level_up ? `${next} is unlocked; at 100% you move up automatically.`
          : (area.unlock_at ?? 50) >= 100 ? `Complete all of ${LEVEL_LABELS[area.level]} to unlock ${next}; you then move up automatically.`
            : `${area.unlock_at ?? 50}% unlocks ${next}; 100% moves you up automatically.`)
          : "This is the top level."}
      </p>
    </div>
  );
}

function AreaCard({ area, onLevel, busy }: { area: ReadinessArea; onLevel: (level: LevelId) => void; busy: boolean }) {
  const scored = area.status === "assessed" && area.score !== null;
  // The card shows how much of the current level is done (it starts from 0
  // at every new level). The area score -- 25 points for each level -- is
  // what counts toward job readiness.
  const perLevel = scored && typeof area.level_progress === "number";
  const shown = perLevel ? area.level_progress as number : area.score as number;
  return (
    <div className={`rd-area status-${area.status}`}>
      <div className="rd-area-head">
        <div>
          <h3>{area.label}</h3>
          <span className="rd-weight">{area.levels_completed?.length ?? 0} of 4 levels completed</span>
        </div>
        <div className="rd-area-score">
          {scored ? <><b>{Math.round(shown)}</b><span>{perLevel ? `% ${LEVEL_LABELS[area.level]}` : "/100"}</span></> : <span className="rd-muted">
            {area.status === "unavailable" ? "Unavailable" : "Not started"}</span>}
        </div>
      </div>
      <div className="rd-bar"><span style={{ width: `${scored ? Math.min(100, shown) : 0}%` }} /></div>
      {scored && <p className="rd-metrics">Area score {Math.round(area.score as number)}/100 · 25 points for each completed level</p>}
      {metricLine(area.metrics) && <p className="rd-metrics">{metricLine(area.metrics)}</p>}
      {area.promoted_from && (
        <p className="rd-promoted">🎉 You completed {LEVEL_LABELS[area.promoted_from]} and moved up to {LEVEL_LABELS[area.level]}.</p>
      )}
      <LevelPicker value={area.level} onChange={onLevel} disabled={busy} gated nextUnlocked={area.can_level_up} unlockAt={area.unlock_at}
        scores={area.level_progress_basis === "level" ? area.level_scores : undefined} />
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
          <p>Progress in your level: {AREA_EXPLANATION[area.agent_name]} Each level you complete adds 25 points to this area's score (Beginner 25, Medium 50, Hard 75, Professional 100); a level counts once it is 100% done. Levels go one at a time: {(area.unlock_at ?? 50) >= 100 ? "complete every problem of your level to unlock the next one, and you move up automatically." : `complete ${area.unlock_at ?? 50}% of your level to unlock the next one; at 100% you move up automatically.`}</p>
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
  const [switching, setSwitching] = useState(false);
  const [saving, setSaving] = useState(false);
  /** A profile with a new target role, waiting for the learner to confirm the reset. */
  const [pendingRole, setPendingRole] = useState<ProfileInput | null>(null);
  /** The skills for the new role, chosen in the role change popup. */
  const [roleSkills, setRoleSkills] = useState<string[]>([]);
  const [roleSkillDraft, setRoleSkillDraft] = useState("");
  const [suggesting, setSuggesting] = useState(false);
  const [roleSkillsError, setRoleSkillsError] = useState("");

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

  const currentRole = cleanProfileText(summary.profile.target_role);
  const isRoleChange = (profile: ProfileInput) => !!currentRole && cleanProfileText(profile.target_role) !== currentRole;
  /** Levels this role kept from the last time the learner worked towards it. */
  const savedRole = (role: string) => summary.role_history?.find((item) => item.role === cleanProfileText(role));

  function requestSave(profile: ProfileInput) {
    if (!isRoleChange(profile)) {
      void saveProfile(profile);
      return;
    }
    // A new role needs its own skills: the ones kept for it last time, the
    // usual ones for a common role, or suggestions for any other role.
    const role = cleanProfileText(profile.target_role);
    const kept = savedRole(role)?.skills ?? [];
    const known = knownRoleSkills(role);
    setPendingRole(profile);
    setRoleSkillDraft("");
    setRoleSkillsError("");
    setRoleSkills(uniqueSkills(kept.length ? kept : known ?? []));
    if (!kept.length && !known) {
      setSuggesting(true);
      suggestRoleSkills(role)
        .then((suggested) => setRoleSkills((current) => (current.length ? current : uniqueSkills(suggested))))
        .catch(() => setRoleSkillsError("I couldn't suggest skills for this role. Add the skills you have or are learning for it."))
        .finally(() => setSuggesting(false));
    }
  }

  /** Roles the learner worked towards before, other than the current one. */
  const otherRoles = (summary.role_history ?? []).filter((item) => item.role && item.role !== currentRole);

  function switchTo(role: string) {
    setSwitching(false);
    const { degree, skills, experience } = summary.profile;
    // requestSave sees the role change and opens the confirm popup with the
    // skills kept for that role.
    requestSave({ target_role: role, degree, skills, experience });
  }

  function confirmRoleChange() {
    if (!pendingRole) return;
    const skills = uniqueSkills([...roleSkills, ...roleSkillDraft.split(",")]);
    if (!skills.length) {
      setRoleSkillsError(`Add at least one skill for ${pendingRole.target_role}.`);
      return;
    }
    void saveProfile({ ...pendingRole, skills });
  }

  async function saveProfile(profile: ProfileInput) {
    const roleChanged = isRoleChange(profile);
    setSaving(true);
    try {
      const before = summary.profile;
      onSummaryChange(await saveLearnerProfile(profile));
      setEditing(false);
      setPendingRole(null);
      // The Job Agent keeps its own copy of the role and skills it searches for.
      void syncJobProfileWithGoal(before, profile);
      if (roleChanged) {
        // A new role has its own levels and points: show them, not the old role's.
        setReadiness(null);
        setHistory([]);
        void load(true);
        onToast(savedRole(profile.target_role)
          ? `Switched back to ${profile.target_role}: your levels and points for it are back.`
          : `Switched to ${profile.target_role}: every level and point starts from zero for this role.`);
      } else {
        onToast("Profile saved. Every agent will use it from your next session.");
      }
    } catch (err) {
      onToast((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  /** For a member who joined before joining meant sharing, and never agreed. */
  async function agreeToShare() {
    try {
      const membership = await setProgressSharing(true);
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
                  Only completed levels count. Each agent earns 25 points for every level it has completed (Beginner 25,
                  Medium 50, Hard 75, Professional 100), and your job readiness is the average over all {readiness.areas.length}{" "}
                  agents. So it shows 25 when every agent's Beginner level is complete, 50 when every Medium level is, and
                  so on. Progress inside a level is shown on each card and counts once the level is complete.{" "}
                  {readiness.overall !== null && `Yours: (${readiness.areas
                    .map((a) => `${a.label} ${Math.round(a.status === "assessed" ? a.score ?? 0 : 0)}`).join(" + ")}) ÷ ${readiness.areas.length} = ${Math.round(readiness.overall)}.`}
                </p>
              </details>
            )}
            <div className="rd-hero-actions">
              <button className="btn btn-primary btn-sm" disabled={loading} onClick={() => void load(true)}>
                {loading ? "Checking…" : "Check again"}
              </button>
              <button className="btn btn-outline btn-sm" onClick={() => setEditing(true)}>Edit profile</button>
              {otherRoles.length > 0 && (
                <button className="btn btn-outline btn-sm" onClick={() => setSwitching(true)}>
                  Switch role ({otherRoles.length + 1})
                </button>
              )}
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
                    {level.source === "derived" ? (
                      <span className="rd-derived-level">
                        <b>{LEVEL_LABELS[level.level]}</b> · follows your other agents' levels
                      </span>
                    ) : (
                      <LevelPicker value={level.level} disabled={busyAgent === level.agent_name}
                        onChange={(next) => void changeLevel(level.agent_name, next)} />
                    )}
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
            {membership.progress_shared ? (
              <p className="rd-muted">You are a member. {orgSharingNotice(membership.organization.name)}</p>
            ) : (
              <>
                <p className="rd-muted">
                  You joined before membership meant sharing, so {membership.organization.name} sees only your name.
                  {" "}{orgSharingNotice(membership.organization.name)}
                </p>
                <button type="button" className="btn btn-outline btn-sm" onClick={() => void agreeToShare()}>Agree and share</button>
              </>
            )}
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
            <LearnerProfileForm initial={profile} submitLabel="Save profile" busy={saving} onSubmit={requestSave} />
          </div>
        </div>
      )}

      {switching && (
        <div className="modal-overlay open" onClick={(e) => e.target === e.currentTarget && setSwitching(false)}>
          <div className="modal rd-modal" role="dialog" aria-modal="true" aria-labelledby="rd-switch-title">
            <div className="rd-modal-head">
              <h2 id="rd-switch-title">Switch role</h2>
              <button type="button" className="link-btn" onClick={() => setSwitching(false)}>Close</button>
            </div>
            <p className="rd-muted">Each role keeps its own levels, skills and points. Pick the one to work on now.</p>
            <ul className="rd-role-list">
              <li className="rd-role-item current">
                <div><strong>{currentRole}</strong><small className="rd-muted">Current role</small></div>
              </li>
              {otherRoles.map((item) => {
                const levels = Object.values(item.levels ?? {}).filter((level): level is LevelId => !!level && level !== "beginner");
                return (
                  <li key={item.role} className="rd-role-item">
                    <div>
                      <strong>{item.role}</strong>
                      <small className="rd-muted">
                        {item.skills?.length ? item.skills.slice(0, 4).join(", ") : "No skills saved"}
                        {levels.length ? ` · ${levels.length} level${levels.length === 1 ? "" : "s"} above Beginner` : ""}
                      </small>
                    </div>
                    <button type="button" className="btn btn-primary btn-sm" disabled={saving} onClick={() => switchTo(item.role)}>Switch</button>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      )}

      {pendingRole && (
        <div className="modal-overlay open rd-confirm-overlay" onClick={(e) => e.target === e.currentTarget && !saving && setPendingRole(null)}>
          <div className="modal rd-modal rd-confirm" role="alertdialog" aria-modal="true" aria-labelledby="rd-confirm-title">
            <h2 id="rd-confirm-title">Change your target role?</h2>
            <p>
              You are changing from <strong>{currentRole}</strong> to <strong>{pendingRole.target_role}</strong>.
            </p>
            {savedRole(pendingRole.target_role) ? (
              <p>
                You have worked towards <strong>{pendingRole.target_role}</strong> before, so its levels and points come back,
                along with anything you completed for it.
              </p>
            ) : (
              <p>
                Every agent's level goes back to <strong>Beginner</strong> and your job-readiness points start again from
                <strong> 0</strong>. You train for this role from the beginning.
              </p>
            )}
            <p className="rd-muted">
              Your progress for <strong>{currentRole}</strong> is kept. Switch back any time and its levels and points return.
            </p>
            <div className="field rd-role-skills">
              <span>Skills for {pendingRole.target_role}</span>
              <small className="rd-muted">
                {suggesting ? "Suggesting skills for this role…"
                  : savedRole(pendingRole.target_role)?.skills?.length ? "Your skills from last time. Change them if you like."
                    : "Suggested for this role. Remove any you don't have, and add your own."}
              </small>
              <SkillsInput skills={roleSkills} onChange={(next) => { setRoleSkills(next); setRoleSkillsError(""); }}
                draft={roleSkillDraft} onDraftChange={setRoleSkillDraft}
                suggestions={summary.profile.skills} suggestionsLabel="Keep from your current skills" />
            </div>
            {roleSkillsError && <p className="form-error" role="alert">{roleSkillsError}</p>}
            <div className="rd-confirm-actions">
              <button type="button" className="btn btn-outline btn-sm" disabled={saving} onClick={() => setPendingRole(null)}>Cancel</button>
              <button type="button" className="btn btn-primary btn-sm" disabled={saving || suggesting} onClick={confirmRoleChange}>
                {saving ? "Changing…" : "Yes, change role"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
