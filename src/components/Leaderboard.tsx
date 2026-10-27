import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchLeaderboard,
  setLeaderboardHidden,
  type Leaderboard as Board,
  type LeaderboardEntry,
  type LeaderboardGroup,
  type LeaderboardScope,
} from "../lib/learnerApi";
import "./Leaderboard.css";

const GROUP_LABELS: Record<LeaderboardGroup, string> = { students: "Students", staff: "Staff" };
const MEDALS = ["🥇", "🥈", "🥉"];
const SPOTLIGHT_MS = 4000;

/** The top 3 by job readiness, a spotlight that rotates through them (whoever
 * just broke into the top 3 first), and the full ranking with the viewer's own
 * rank. Students: their organization's board and the whole platform. Staff:
 * their organization's staff board, ranked on their students. Owners and
 * admins: their organization's students and staff boards. */
export default function Leaderboard({ defaultScope = "auto", onToast, compact = false }: {
  defaultScope?: LeaderboardScope | "auto"; onToast?: (message: string) => void; compact?: boolean;
}) {
  const [scope, setScope] = useState<LeaderboardScope | "auto">(defaultScope);
  const [group, setGroup] = useState<LeaderboardGroup | undefined>(undefined);
  const [board, setBoard] = useState<Board | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [spot, setSpot] = useState(0);
  const [showAll, setShowAll] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setBoard(await fetchLeaderboard(scope, group));
      setError("");
    } catch (err) {
      const message = (err as Error).message;
      // Not allowed this scope (e.g. no organization): fall back to the viewer's own.
      if (scope !== "auto") setScope("auto");
      else setError(message);
    } finally {
      setLoading(false);
    }
  }, [scope, group]);

  useEffect(() => { void load(); }, [load]);

  // Newcomers to the top 3 get the spotlight first.
  const spotlight = useMemo(() => {
    const top = board?.top ?? [];
    return [...top.filter((e) => e.new_in_top), ...top.filter((e) => !e.new_in_top)];
  }, [board]);

  useEffect(() => {
    setSpot(0);
    if (spotlight.length < 2) return;
    const timer = window.setInterval(() => setSpot((current) => (current + 1) % spotlight.length), SPOTLIGHT_MS);
    return () => window.clearInterval(timer);
  }, [spotlight]);

  async function toggleHidden() {
    if (!board) return;
    try {
      await setLeaderboardHidden(!board.hidden);
      onToast?.(board.hidden ? "You are on the leaderboard again." : "You are hidden from leaderboards.");
      await load();
    } catch (err) {
      onToast?.((err as Error).message);
    }
  }

  const featured = spotlight[spot];
  const rest = (board?.entries ?? []).slice(3);
  const shown = showAll ? rest : rest.slice(0, compact ? 5 : 10);

  return (
    <section className="lb">
      <header className="lb-head">
        <div>
          <span className="rd-kicker">Leaderboard · job readiness</span>
          <h2>{board?.group === "staff" ? "Top staff" : "Top learners"}{board?.scope === "organization" && board.organization ? ` at ${board.organization.name}` : " on SkillDARA"}</h2>
        </div>
        <div className="lb-controls">
          {board && board.allowed_scopes.length > 1 && (
            <div className="lb-switch" role="tablist" aria-label="Leaderboard scope">
              {board.allowed_scopes.map((value) => (
                <button key={value} type="button" role="tab" aria-selected={board.scope === value} className={board.scope === value ? "on" : ""}
                  onClick={() => setScope(value)}>{value === "platform" ? "Whole platform" : "My organization"}</button>
              ))}
            </div>
          )}
          {board && board.allowed_groups.length > 1 && (
            <div className="lb-switch" role="tablist" aria-label="Leaderboard group">
              {board.allowed_groups.map((value) => (
                <button key={value} type="button" role="tab" aria-selected={board.group === value} className={board.group === value ? "on" : ""}
                  onClick={() => setGroup(value)}>{GROUP_LABELS[value]}</button>
              ))}
            </div>
          )}
        </div>
      </header>

      {error && <p className="form-error" role="alert">{error}</p>}
      {loading && !board && <div className="lb-skeleton" />}

      {board && board.top.length === 0 && (
        <p className="rd-muted lb-empty">{board.group === "staff" ? "No staff yet. Staff are ranked on the students who join with their join codes."
          : "No scores yet. Check your job readiness to get on the board."}</p>
      )}
      {board?.group === "staff" && board.top.length > 0 && (
        <p className="rd-muted lb-note">Staff score: 70% their students' average job readiness + 30% the share of their students active in the last 14 days.</p>
      )}

      {board && board.top.length > 0 && (
        <>
          {featured && (
            <div className={`lb-spotlight${featured.new_in_top ? " new" : ""}`} aria-live="polite" key={featured.user_id}>
              <span className="lb-spot-medal" aria-hidden="true">{MEDALS[featured.rank - 1]}</span>
              <div>
                {featured.new_in_top && <span className="lb-new">New in Top 3</span>}
                <b>{featured.name}{featured.is_me ? " (you)" : ""}</b>
                <small>#{featured.rank} · {Math.round(featured.score)} {featured.staff ? "staff score" : "readiness"}{featured.organization ? ` · ${featured.organization}` : ""}</small>
                {featured.staff && <small>{staffLine(featured.staff)}</small>}
              </div>
              {spotlight.length > 1 && (
                <div className="lb-dots" aria-hidden="true">{spotlight.map((e, i) => <i key={e.user_id} className={i === spot ? "on" : ""} />)}</div>
              )}
            </div>
          )}

          <ol className="lb-podium" aria-label="Top 3">
            {[1, 0, 2].map((index) => board.top[index]).filter(Boolean).map((entry) => (
              <PodiumPlace key={entry.user_id} entry={entry} />
            ))}
          </ol>

          {rest.length > 0 && (
            <ol className="lb-list" start={4}>
              {shown.map((entry) => (
                <li key={entry.user_id} className={entry.is_me ? "me" : ""}>
                  <span className="lb-rank">#{entry.rank}</span>
                  <span className="lb-name">{entry.name}{entry.is_me ? " (you)" : ""}{entry.organization && <small>{entry.organization}</small>}
                    {entry.staff && <small>{staffLine(entry.staff)}</small>}</span>
                  <span className="lb-score">{Math.round(entry.score)}</span>
                </li>
              ))}
            </ol>
          )}
          {rest.length > shown.length && !showAll && (
            <button type="button" className="link-btn" onClick={() => setShowAll(true)}>Show all {board.entries.length}</button>
          )}
        </>
      )}

      {board && (
        <footer className="lb-foot">
          <span>
            {board.hidden ? "You are hidden from leaderboards."
              : board.me ? <>Your rank: <b>#{board.me.rank}</b> of {board.total} · {Math.round(board.me.score)} readiness</>
                : board.group === "students" && board.allowed_groups.length === 1 ? "Check your job readiness to get a rank." : `${board.total} ranked`}
          </span>
          {board.allowed_groups.length === 1 && (
            <button type="button" className="link-btn" onClick={() => void toggleHidden()}>{board.hidden ? "Show me" : "Hide me"}</button>
          )}
        </footer>
      )}
    </section>
  );
}

function staffLine(staff: NonNullable<LeaderboardEntry["staff"]>): string {
  return `${staff.students} student${staff.students === 1 ? "" : "s"} · avg readiness ${Math.round(staff.average_readiness)} · ${staff.active_percent}% active`;
}

function PodiumPlace({ entry }: { entry: LeaderboardEntry }) {
  return (
    <li className={`lb-place place-${entry.rank}${entry.is_me ? " me" : ""}${entry.new_in_top ? " new" : ""}`}>
      <span className="lb-medal" aria-hidden="true">{MEDALS[entry.rank - 1]}</span>
      <span className="lb-avatar" aria-hidden="true">{entry.name.slice(0, 1).toUpperCase()}</span>
      <b>{entry.name}{entry.is_me ? " (you)" : ""}</b>
      {entry.organization && <small>{entry.organization}</small>}
      {entry.new_in_top && <span className="lb-new">New</span>}
      <strong>{Math.round(entry.score)}</strong>
      <div className="lb-step"><span>{entry.rank}</span></div>
    </li>
  );
}

const MINI_MEDALS = ["🥇", "🥈", "🥉"];

/** The top 3, in a card on the right of the chat home page: the learner's
 * organization when they are in one, else the whole platform. */
export function TopPerformers({ onOpen }: { onOpen?: () => void }) {
  const [board, setBoard] = useState<Board | null>(null);
  useEffect(() => {
    let active = true;
    fetchLeaderboard("auto").then((result) => { if (active) setBoard(result); }).catch(() => undefined);
    return () => { active = false; };
  }, []);
  if (!board || board.top.length === 0) return null;
  const where = board.scope === "organization" && board.organization ? board.organization.name : "SkillDARA";
  return (
    <aside className="lb-side" aria-label={`Top 3 at ${where}`}>
      <header>
        <span className="lb-side-icon" aria-hidden="true">🏆</span>
        <div>
          <b>Top {board.group === "staff" ? "staff" : "performers"}</b>
          <small>{where}</small>
        </div>
      </header>
      <ol>
        {board.top.map((entry) => (
          <li key={entry.user_id} className={entry.is_me ? "me" : ""}>
            <span className="lb-side-medal" aria-hidden="true">{MINI_MEDALS[entry.rank - 1]}</span>
            <span className="lb-side-name">
              <b>{entry.name}{entry.is_me ? " (you)" : ""}</b>
              {entry.new_in_top ? <span className="lb-new">New in Top 3</span>
                : <small>{entry.staff ? `${entry.staff.students} students` : entry.organization ?? `#${entry.rank}`}</small>}
            </span>
            <strong>{Math.round(entry.score)}</strong>
          </li>
        ))}
      </ol>
      {board.me && board.me.rank > 3 && <p className="lb-side-me">Your rank: <b>#{board.me.rank}</b> of {board.total}</p>}
      {onOpen && <button type="button" className="lb-side-open" onClick={onOpen}>View leaderboard →</button>}
    </aside>
  );
}
