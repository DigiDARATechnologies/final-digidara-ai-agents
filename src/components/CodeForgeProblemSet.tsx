import { useEffect, useMemo, useState } from "react";
import {
  getAssessmentOverview,
  getProblemSet,
  startAssessment,
  type Assessment,
  type AssessmentOverview,
  type ProblemSet,
  type ProblemSetItem,
  type ProblemSetLanguage,
} from "../lib/codeforgeApi";
import "./CodeForgeProblemSet.css";

interface Props {
  open: boolean;
  sessionToken?: string;
  /** Only this course's languages, starting on this technology. */
  courseSlug?: string;
  technologySlug?: string;
  onClose: () => void;
  onOpenProblem: (target: { courseSlug: string; technologySlug: string; technologyName: string; problem: ProblemSetItem; problems: ProblemSetItem[] }) => void;
  /** Starts or continues a Professional assessment in the chat. */
  onAssessment: (assessment: Assessment, technology: { slug: string; name: string; courseSlug?: string }) => void;
}

function when(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : "";
}

/** The Professional level: timed assessments instead of a problem list. */
function AssessmentPanel({ overview, busy, onStart }: { overview: AssessmentOverview; busy: boolean; onStart: () => void }) {
  const name = overview.technology.name;
  if (!overview.available) {
    return <section className="ps-assess off"><b>Professional assessment</b><span>Coming soon for {name}. Available now for Python, MySQL and JavaScript.</span></section>;
  }
  const active = overview.active;
  return (
    <section className={`ps-assess${overview.eligible ? "" : " off"}`} aria-label="Professional assessment">
      <div className="ps-assess-main">
        <b>{overview.eligible ? "🎯" : "🔒"} Professional assessment · {name}</b>
        <span>
          {overview.minutes} minutes · 3 problems (a Hard problem, an Expert problem, a real-world task) · no AI tutor ·
          {" "}{overview.pass_mark}/100 passes · <b>{Math.min(overview.passed, 3)} of 3 passed</b>
        </span>
        {!overview.eligible && <span>Unlocks at the Professional level: solve every Hard problem first.</span>}
      </div>
      {overview.eligible && (
        <button type="button" className="ps-assess-btn" disabled={busy} onClick={onStart}>
          {busy ? "Starting…" : active ? `Continue (ends ${when(active.deadline_at)})` : "Start assessment"}
        </button>
      )}
      {overview.attempts.length > 0 && (
        <ul className="ps-attempts">
          {overview.attempts.slice(0, 5).map((attempt) => (
            <li key={attempt.id}>
              <span>{when(attempt.finished_at ?? attempt.started_at)}</span>
              <b className={attempt.passed ? "ok" : ""}>{attempt.score ?? 0}/100 · {attempt.passed ? "Passed" : attempt.status === "expired" ? "Time up" : "Not passed"}</b>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

const DIFFICULTIES = ["Easy", "Medium", "Hard"] as const;
const LEVEL_OF: Record<string, string> = { Easy: "Beginner", Medium: "Medium", Hard: "Hard" };

function StatusIcon({ problem }: { problem: ProblemSetItem }) {
  if (problem.locked) return <span className="ps-status locked" title="Locked">🔒</span>;
  if (problem.progress === "Solved") return <span className="ps-status solved" title="Solved">✓</span>;
  if (problem.attempts > 0) return <span className="ps-status tried" title="Attempted">◐</span>;
  return <span className="ps-status" aria-hidden="true" />;
}

/** Every language, and every problem of the chosen one, the way LeetCode lists
 * them. Only the learner's level (and levels they finished) open; the next
 * level unlocks once every problem of their level is solved. */
export default function CodeForgeProblemSet({ open, sessionToken, courseSlug, technologySlug, onClose, onOpenProblem, onAssessment }: Props) {
  const [overview, setOverview] = useState<AssessmentOverview | null>(null);
  const [starting, setStarting] = useState(false);
  const [data, setData] = useState<ProblemSet | null>(null);
  const [language, setLanguage] = useState<string | undefined>(technologySlug);

  // Opened again for another course or technology: start there.
  useEffect(() => { if (open) setLanguage(technologySlug); }, [open, technologySlug, courseSlug]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [difficulty, setDifficulty] = useState<string>("");
  const [status, setStatus] = useState<string>("");

  useEffect(() => {
    if (!open || !sessionToken) return;
    let active = true;
    setLoading(true);
    getProblemSet(sessionToken, language, courseSlug)
      .then((result) => { if (active) { setData(result); setError(""); } })
      .catch((err) => { if (active) setError((err as Error).message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [open, sessionToken, language, courseSlug]);

  // The Professional assessment for the language on screen.
  const shownLanguage = data?.technology_slug;
  useEffect(() => {
    if (!open || !sessionToken || !shownLanguage) return;
    let active = true;
    getAssessmentOverview(sessionToken, shownLanguage).then((o) => { if (active) setOverview(o); }).catch(() => { if (active) setOverview(null); });
    return () => { active = false; };
  }, [open, sessionToken, shownLanguage]);

  async function start() {
    if (!sessionToken || !overview) return;
    setStarting(true);
    try {
      const assessment = overview.active ?? (await startAssessment(sessionToken, overview.technology.slug)).assessment;
      onAssessment(assessment, { ...overview.technology, courseSlug });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setStarting(false);
    }
  }

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const current: ProblemSetLanguage | undefined = data?.languages.find((l) => l.slug === data.technology_slug);
  const rows = useMemo(() => (data?.problems ?? []).filter((p) => {
    if (difficulty && p.difficulty !== difficulty) return false;
    if (status === "solved" && p.progress !== "Solved") return false;
    if (status === "todo" && (p.progress === "Solved" || p.locked)) return false;
    if (status === "open" && p.locked) return false;
    const text = search.trim().toLowerCase();
    return !text || p.name.toLowerCase().includes(text) || p.topic_name.toLowerCase().includes(text) || String(p.number) === text;
  }), [data, difficulty, status, search]);

  if (!open) return null;
  const level = data?.level ?? "Easy";
  const mine = current?.counts[level];
  const nextLevel = level === "Easy" ? "Medium" : level === "Medium" ? "Hard" : null;

  return (
    <div className="ps-overlay" role="dialog" aria-modal="true" aria-label="Problem list">
      <div className="ps-panel">
        <header className="ps-head">
          <div>
            <h2>Problems</h2>
            {data && (
              <p>
                Your Coding level: <b>{data.level_name}</b> · {level} problems are open
                {nextLevel && mine ? ` · solve all ${mine.total} of them (${mine.solved} done) to unlock ${nextLevel}` : ""}
              </p>
            )}
          </div>
          <button type="button" className="ps-close" aria-label="Close" onClick={onClose}>×</button>
        </header>

        <nav className="ps-langs" aria-label="Languages">
          {data?.languages.map((lang) => {
            const solved = DIFFICULTIES.reduce((sum, d) => sum + lang.counts[d].solved, 0);
            const total = DIFFICULTIES.reduce((sum, d) => sum + lang.counts[d].total, 0);
            return (
              <button key={lang.slug} type="button" className={lang.slug === data.technology_slug ? "on" : ""}
                onClick={() => setLanguage(lang.slug)}>
                {lang.name}<span>{solved}/{total}</span>
              </button>
            );
          })}
        </nav>

        {current && (
          <section className="ps-progress" aria-label={`${current.name} progress`}>
            {DIFFICULTIES.map((d) => {
              const count = current.counts[d];
              const lockedLevel = DIFFICULTIES.indexOf(d) > DIFFICULTIES.indexOf(level);
              return (
                <div key={d} className={`ps-prog ps-${d.toLowerCase()}${lockedLevel ? " locked" : ""}`}>
                  <span>{lockedLevel ? "🔒 " : ""}{LEVEL_OF[d]} · {d}</span>
                  <b>{count.solved}<small>/{count.total}</small></b>
                  <i><em style={{ width: `${count.total ? (count.solved / count.total) * 100 : 0}%` }} /></i>
                </div>
              );
            })}
          </section>
        )}

        {overview && <AssessmentPanel overview={overview} busy={starting} onStart={() => void start()} />}

        <div className="ps-tools">
          <input type="search" placeholder="Search questions or topics" value={search} onChange={(e) => setSearch(e.target.value)} />
          <select value={difficulty} aria-label="Difficulty" onChange={(e) => setDifficulty(e.target.value)}>
            <option value="">Difficulty</option>
            {DIFFICULTIES.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
          <select value={status} aria-label="Status" onChange={(e) => setStatus(e.target.value)}>
            <option value="">Status</option>
            <option value="open">Open to me</option>
            <option value="todo">To do</option>
            <option value="solved">Solved</option>
          </select>
          <span className="ps-count">{rows.filter((r) => r.progress === "Solved").length}/{rows.length} solved</span>
        </div>

        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="ps-table" role="table" aria-busy={loading}>
          {rows.map((problem) => (
            <button key={problem.id} type="button" role="row" className={`ps-row${problem.locked ? " locked" : ""}`}
              disabled={problem.locked}
              title={problem.locked ? `Locked: finish every ${level} problem to unlock ${problem.difficulty}.` : `Open ${problem.name}`}
              onClick={() => data && current && onOpenProblem({
                courseSlug: courseSlug ?? current.course_slug, technologySlug: current.slug, technologyName: current.name, problem,
                problems: data.problems.filter((p) => !p.locked),
              })}>
              <StatusIcon problem={problem} />
              <span className="ps-title"><b>{problem.number}. {problem.name}</b><small>{problem.topic_name}</small></span>
              <span className="ps-best">{problem.attempts > 0 ? `best ${problem.best_score}` : ""}</span>
              <span className={`ps-diff ps-${problem.difficulty.toLowerCase()}`}>{problem.difficulty === "Medium" ? "Med." : problem.difficulty}</span>
            </button>
          ))}
          {!loading && rows.length === 0 && <p className="ps-empty">No problems match.</p>}
          {loading && !data && <div className="ps-skeleton" />}
        </div>
      </div>
    </div>
  );
}
