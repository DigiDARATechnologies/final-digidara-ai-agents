import { useEffect, useState } from "react";
import { fetchTeamMessages, markTeamMessagesRead, type TeamMessage } from "../lib/learnerApi";

function when(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);   // the server stores UTC without a marker
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString([], { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** Opens by itself when the learner signs in (or opens the app) and the
 * SkillDARA team has sent them something they haven't seen -- e.g. "the
 * problem you reported is solved". Closing it marks them read. */
export default function TeamMessagesPopup({ userId }: { userId: string }) {
  const [unread, setUnread] = useState<TeamMessage[]>([]);

  useEffect(() => {
    let active = true;
    fetchTeamMessages()
      .then(({ messages }) => { if (active) setUnread(messages.filter((message) => !message.read_at)); })
      .catch(() => undefined);   // never block the app on this
    return () => { active = false; };
  }, [userId]);

  if (!unread.length) return null;

  function close() {
    setUnread([]);
    void markTeamMessagesRead().catch(() => undefined);
  }

  return (
    <div className="modal-overlay open" onClick={(event) => event.target === event.currentTarget && close()}>
      <div className="modal-card team-msg-card" role="dialog" aria-modal="true" aria-labelledby="teamMsgTitle">
        <div className="modal-head">
          <h3 id="teamMsgTitle">{unread.length === 1 ? "A message from the SkillDARA team" : `${unread.length} messages from the SkillDARA team`}</h3>
          <button type="button" className="icon-btn" aria-label="Close" onClick={close}>✕</button>
        </div>
        <div className="modal-body">
          <div className="team-msg-list">
            {unread.map((message) => (
              <div key={message.id} className="team-msg-item">
                {message.report_message && <div className="team-msg-report">About your report: “{message.report_message}”</div>}
                <p>{message.body}</p>
                <small>{when(message.created_at)}</small>
              </div>
            ))}
          </div>
          <button type="button" className="btn btn-primary btn-full" onClick={close}>OK, got it</button>
        </div>
      </div>
    </div>
  );
}
