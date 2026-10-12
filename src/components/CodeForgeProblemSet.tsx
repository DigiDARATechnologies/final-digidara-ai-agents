import { useEffect, useMemo, useState } from "react";
import { getProblemSet, type ProblemSet, type ProblemSetItem, type ProblemSetLanguage } from "../lib/codeforgeApi";
import "./CodeForgeProblemSet.css";

interface Props {
  open: boolean;
  sessionToken?: string;
  onClose: () => void;
  onOpenProblem: (target: { courseSlug: string; technologySlug: string; technologyName: string; problem: ProblemSetItem }) => void;
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
export default function CodeForgeProblemSet({ open, sessionToken, onClose, onOpenProblem }: Props) {
  const [data, setData] = useState<ProblemSet | null>(null);
  const [language, setLanguage] = useState<string | undefined>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [difficulty, setDifficulty] = useState<string>("");
  const [status, setStatus] = useState<string>("");

  useEffect(() => {
    if (!open || !sessionToken) return;
    let active = true;
    setLoading(true);
    getProblemSet(sessionToken, language)
      .then((result) => { if (active) { setData(result); setError(""); } })
      .catch((err) => { if (active) setError((err as Error).message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [open, sessionToken, language]);

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
                courseSlug: current.course_slug, technologySlug: current.slug, technologyName: current.name, problem,
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
