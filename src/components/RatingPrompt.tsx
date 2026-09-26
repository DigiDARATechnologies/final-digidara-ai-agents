import { useEffect, useState } from "react";
import type { Agent } from "../types";
import { getMyRating, markAsked, shouldAskForRating, submitRating } from "../lib/ratings";

interface Props {
  /** The agent being used right now, or null when no live agent chat is open. */
  agent: Agent | null;
  chatId: string | null;
  userId: string;
  onToast: (message: string) => void;
}

const ASK_AFTER_SECONDS = 5 * 60;
const TICK_SECONDS = 10;
const LABELS = ["Poor", "Fair", "Good", "Very good", "Excellent"];

export default function RatingPrompt({ agent, chatId, userId, onToast }: Props) {
  const [open, setOpen] = useState(false);
  const [stars, setStars] = useState(0);
  const [hover, setHover] = useState(0);
  const [target, setTarget] = useState<{ agent: Agent; chatId: string } | null>(null);

  const agentId = agent?.id;
  const rateable = Boolean(agent?.kind && chatId);

  // Count the time this chat is open and the tab is visible; ask once it reaches five minutes.
  useEffect(() => {
    if (!rateable || !agent || !chatId || open) return;
    if (!shouldAskForRating(userId, agent.id, chatId)) return;
    let seconds = 0;
    const id = window.setInterval(() => {
      if (document.visibilityState !== "visible") return;
      seconds += TICK_SECONDS;
      if (seconds >= ASK_AFTER_SECONDS) {
        window.clearInterval(id);
        markAsked(userId, agent.id, chatId);
        setTarget({ agent, chatId });
        setStars(getMyRating(userId, agent.id) ?? 0);
        setOpen(true);
      }
    }, TICK_SECONDS * 1000);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agentId, chatId, rateable, userId, open]);

  if (!open || !target) return null;

  const shown = hover || stars;
  const close = () => {
    setOpen(false);
    setHover(0);
  };
  const submit = () => {
    if (!stars) return;
    submitRating(userId, target.agent.id, stars);
    onToast(`Thanks for rating ${target.agent.name}!`);
    close();
  };

  return (
    <div className="rp-card" role="dialog" aria-label={`Rate ${target.agent.name}`}>
      <button type="button" className="rp-close" aria-label="Dismiss" onClick={close}>×</button>
      <div className="rp-head">
        <span className="rp-icon" style={{ background: `color-mix(in srgb, ${target.agent.color} 28%, transparent)` }}>{target.agent.icon}</span>
        <div>
          <b>How is {target.agent.name} working for you?</b>
          <p>Your rating helps other learners choose the right agent.</p>
        </div>
      </div>
      <div className="rp-stars" role="radiogroup" aria-label="Star rating" onMouseLeave={() => setHover(0)}>
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={stars === n}
            aria-label={`${n} star${n > 1 ? "s" : ""}`}
            className={n <= shown ? "on" : ""}
            onMouseEnter={() => setHover(n)}
            onClick={() => setStars(n)}
          >
            ★
          </button>
        ))}
        <span className="rp-label">{shown ? LABELS[shown - 1] : "Tap a star"}</span>
      </div>
      <div className="rp-actions">
        <button type="button" className="btn btn-outline" onClick={close}>Not Now</button>
        <button type="button" className="btn btn-primary" disabled={!stars} onClick={submit}>Submit</button>
      </div>
    </div>
  );
}
