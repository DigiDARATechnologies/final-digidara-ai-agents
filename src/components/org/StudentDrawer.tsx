import { useCallback, useEffect, useState } from "react";
import ClassSelect from "./ClassSelect";
import { ScoreRing } from "../ReadinessView";
import {
  BAND_TONE,
  LEVEL_IDS,
  LEVEL_LABELS,
  refreshMemberReadiness,
  removeOrgMember,
  setMemberLevel,
  updateOrgMember,
  type LevelId,
  type OrgMember,
} from "../../lib/learnerApi";
import {
  CLASS_KINDS,
  CLASS_LABELS,
  fetchMemberConversation,
  fetchMemberDetail,
  updateMemberClass,
  type ClassFields,
  type ClassOptions,
  type MemberDetail,
  type Transcript,
} from "../../lib/orgApi";
import { renderMessageText } from "../../lib/messageText";

interface Props {
  orgId: string;
  member: OrgMember;
  isOwner: boolean;
  options: ClassOptions;
  agentLabels: Record<string, string>;
  onClose: () => void;
  onChanged: () => void;
  onToast: (message: string) => void;
}

const TABS = ["Overview", "Chats", "Activity", "Manage"] as const;
type Tab = (typeof TABS)[number];

function when(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`).toLocaleString(undefined,
    { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

/** Everything about one learner, opened from the students table. Opening it
 * and every chat is recorded in the organization's access log. */
export default function StudentDrawer({ orgId, member, isOwner, options, agentLabels, onClose, onChanged, onToast }: Props) {
  const [detail, setDetail] = useState<MemberDetail | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<Tab>("Overview");
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [busy, setBusy] = useState(false);
  const [classFields, setClassFields] = useState<ClassFields>({ department: member.department, year: member.year, section: member.section });

  const load = useCallback(async () => {
    if (!member.progress_shared) return;
    try {
      setDetail(await fetchMemberDetail(orgId, member.member_id));
      setError("");
    } catch (err) {
      setError((err as Error).message);
    }
  }, [orgId, member.member_id, member.progress_shared]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && (transcript ? setTranscript(null) : onClose());
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, transcript]);

  async function run(action: () => Promise<unknown>, message: string, reload = true) {
    setBusy(true);
    try {
      await action();
      onToast(message);
      onChanged();
      if (reload) await load();
    } catch (err) {
      onToast((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function openChat(conversationId: string) {
    try {
      setTranscript(await fetchMemberConversation(orgId, member.member_id, conversationId));
    } catch (err) {
      onToast((err as Error).message);
    }
  }

  const readiness = detail?.readiness;
  const classLine = [member.department, member.year, member.section].filter(Boolean).join(" · ");

  return (
    <div className="org-drawer-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <aside className="org-drawer" role="dialog" aria-modal="true" aria-label={`${member.name} details`}>
        <header className="org-drawer-head">
          <span className="org-avatar lg" aria-hidden="true">{member.name.slice(0, 1).toUpperCase()}</span>
          <div className="org-drawer-title">
            <h2>{member.name}</h2>
            <span>{member.email}{member.external_id ? ` · ${member.external_id}` : ""}</span>
            {classLine && <span className="org-chip">{classLine}</span>}
          </div>
          <button type="button" className="org-icon-btn" aria-label="Close" onClick={onClose}>×</button>
        </header>

        {!member.progress_shared ? (
          <p className="org-empty">This learner joined before joining meant sharing and has not agreed yet, so only their name is visible.</p>
        ) : (
          <>
            <nav className="org-tabs small" role="tablist">
              {TABS.map((name) => (
                <button key={name} type="button" role="tab" aria-selected={tab === name} className={tab === name ? "on" : ""}
                  onClick={() => setTab(name)}>{name}{name === "Chats" && detail ? ` (${detail.conversations.length})` : ""}</button>
              ))}
            </nav>
            {error && <p className="form-error" role="alert">{error}</p>}
            {!detail && !error && <div className="org-skeleton" />}

            {detail && tab === "Overview" && (
              <div className="org-drawer-body">
                <section className="org-drawer-hero">
                  <ScoreRing score={readiness?.overall ?? null} band={readiness?.band ?? "not_started"} size={96} />
                  <div>
                    <span className="rd-kicker">Job readiness</span>
                    <b>{readiness ? readiness.band_label : "Not checked yet"}</b>
                    <span className="rd-muted">{readiness ? `Checked ${when(readiness.computed_at)}` : ""}</span>
                    <span>{detail.profile.target_role || "No target role"}{detail.profile.degree ? ` · ${detail.profile.degree}` : ""}
                      {` · ${detail.profile.experience === "experienced" ? "Experienced" : "Fresher"}`}</span>
                  </div>
                </section>
                <div className="rd-chips">{detail.profile.skills.map((s) => <span key={s} className="lp-chip">{s}</span>)}</div>

                <h3>Agents and levels</h3>
                <div className="org-agent-grid">
                  {detail.levels.map((level) => {
                    const area = readiness?.areas[level.agent_name];
                    return (
                      <div key={level.agent_name} className="org-agent-card">
                        <div><b>{level.agent_label}</b>{area?.leveled !== false && <span className="org-chip">{LEVEL_LABELS[level.level]}</span>}</div>
                        {area?.leveled === false ? (
                          <small>No levels · {area.score != null ? `score ${Math.round(area.score)}/100` : "not started"}</small>
                        ) : area ? (
                          <>
                            <div className="org-level-steps">
                              {LEVEL_IDS.map((id) => (
                                <i key={id} className={area.levels_completed?.includes(id) ? "done" : id === level.level ? "now" : ""}
                                  title={`${LEVEL_LABELS[id]}: ${Math.round(area.level_scores?.[id] ?? (id === level.level ? area.level_progress ?? 0 : 0))}%`} />
                              ))}
                            </div>
                            <small>{area.levels_completed?.length ?? 0} of 4 levels · {area.level_progress != null ? `${Math.round(area.level_progress)}% of ${LEVEL_LABELS[level.level]}` : "not started"}</small>
                          </>
                        ) : <small className="rd-muted">{level.source === "derived" ? "Follows the other agents" : "No activity yet"}</small>}
                      </div>
                    );
                  })}
                </div>

                {readiness && readiness.next_steps.length > 0 && (
                  <>
                    <h3>What they should do next</h3>
                    <ol className="rd-steps">{readiness.next_steps.map((step) => <li key={step}>{step}</li>)}</ol>
                  </>
                )}
                {detail.career_plan?.headline && (
                  <>
                    <h3>Career plan</h3>
                    <p><b>{detail.career_plan.headline}</b> {detail.career_plan.summary}</p>
                  </>
                )}
                {detail.memories.length > 0 && (
                  <>
                    <h3>What the agents remember</h3>
                    <ul className="org-memories">{detail.memories.slice(0, 12).map((m, i) => <li key={i}>{m.text}</li>)}</ul>
                  </>
                )}
                {detail.role_history.length > 1 && (
                  <p className="rd-muted">Roles worked towards: {detail.role_history.map((r) => r.role).join(", ")}</p>
                )}
              </div>
            )}

            {detail && tab === "Chats" && (
              <div className="org-drawer-body">
                <p className="org-notice">Opening a chat is recorded, and the learner can see that you viewed it.</p>
                {detail.conversations.length === 0 ? <p className="org-empty">No chats yet.</p> : (
                  <ul className="org-chat-list">
                    {detail.conversations.map((c) => (
                      <li key={c.id}>
                        <button type="button" onClick={() => void openChat(c.id)}>
                          <b>{c.title || "Untitled chat"}</b>
                          <span>{agentLabels[c.agent_id] ?? c.agent_id} · {c.messages} messages · {when(c.updated_at)}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {detail && tab === "Activity" && (
              <div className="org-drawer-body">
                {detail.activity.length === 0 ? <p className="org-empty">No agent activity yet.</p> : (
                  <table className="org-table compact">
                    <thead><tr><th>Agent</th><th>Requests</th><th>Last used</th></tr></thead>
                    <tbody>{detail.activity.map((a) => (
                      <tr key={a.agent_name}><td>{agentLabels[a.agent_name] ?? a.agent_name}</td><td>{a.requests}</td><td>{when(a.last_at)}</td></tr>
                    ))}</tbody>
                  </table>
                )}
                <h3>Readiness over time</h3>
                {detail.readiness_history.length < 2 ? <p className="rd-muted">The trend appears after a few checks.</p> : (
                  <ul className="org-history">
                    {detail.readiness_history.slice(-10).reverse().map((h) => (
                      <li key={h.computed_at}><span>{when(h.computed_at)}</span>
                        <b className={`og-band tone-${BAND_TONE[h.band]}`}>{h.overall === null ? "–" : Math.round(h.overall)}</b></li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {detail && tab === "Manage" && (
              <div className="org-drawer-body">
                <h3>Class</h3>
                <div className="org-class-grid">
                  {CLASS_KINDS.map((kind) => (
                    <ClassSelect key={kind} label={CLASS_LABELS[kind]} value={classFields[kind] ?? ""} options={options[kind]}
                      maxLength={kind === "department" ? 120 : 40}
                      onChange={(value) => setClassFields((current) => ({ ...current, [kind]: value || null }))} />
                  ))}
                </div>
                <button type="button" className="btn btn-primary btn-sm" disabled={busy}
                  onClick={() => void run(() => updateMemberClass(orgId, member.member_id, classFields), `${member.name}'s class saved.`, false)}>
                  Save class
                </button>

                <h3>Levels</h3>
                <div className="org-level-edit">
                  {detail.levels.filter((l) => l.source !== "derived").map((level) => (
                    <label key={level.agent_name}>
                      <span>{level.agent_label}</span>
                      <select value={level.level} disabled={busy} onChange={(e) => void run(
                        () => setMemberLevel(orgId, member.member_id, level.agent_name, e.target.value as LevelId),
                        `${level.agent_label} set to ${LEVEL_LABELS[e.target.value as LevelId]}.`)}>
                        {LEVEL_IDS.map((id) => <option key={id} value={id}>{LEVEL_LABELS[id]}</option>)}
                      </select>
                    </label>
                  ))}
                </div>

                <div className="org-actions">
                  <button className="btn btn-outline btn-sm" disabled={busy}
                    onClick={() => void run(() => refreshMemberReadiness(orgId, member.member_id), `Readiness checked for ${member.name}.`)}>
                    Check readiness now
                  </button>
                  {isOwner && member.role !== "owner" && (
                    <button className="btn btn-outline btn-sm" disabled={busy}
                      onClick={() => void run(() => updateOrgMember(orgId, member.member_id, { role: member.role === "admin" ? "member" : "admin" }),
                        member.role === "admin" ? `${member.name} is now a learner.` : `${member.name} is now an admin.`, false)}>
                      {member.role === "admin" ? "Make learner" : "Make admin"}
                    </button>
                  )}
                  {member.role !== "owner" && (
                    <button className="btn btn-outline btn-sm btn-danger" disabled={busy}
                      onClick={() => window.confirm(`Remove ${member.name} from the organization? Their account stays.`)
                        && void run(() => removeOrgMember(orgId, member.member_id), `${member.name} was removed.`, false).then(onClose)}>
                      Remove from organization
                    </button>
                  )}
                </div>
              </div>
            )}
          </>
        )}

        {transcript && (
          <div className="org-transcript" role="dialog" aria-label={transcript.title}>
            <header>
              <button type="button" className="link-btn" onClick={() => setTranscript(null)}>← Back to chats</button>
              <b>{transcript.title}</b>
              <span className="rd-muted">{agentLabels[transcript.agent_id] ?? transcript.agent_id}</span>
            </header>
            <div className="org-transcript-body">
              {transcript.messages.map((m, i) => (
                <div key={i} className={`org-msg ${m.role === "user" ? "user" : "agent"}`}>
                  <div className="org-msg-text">{m.role === "user" ? m.content : renderMessageText(m.content)}</div>
                  <small>{m.role === "user" ? member.name : "Agent"} · {m.time}</small>
                </div>
              ))}
              {transcript.messages.length === 0 && <p className="org-empty">This chat has no messages.</p>}
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}
