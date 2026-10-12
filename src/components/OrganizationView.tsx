import { useEffect, useState } from "react";
import JoinOrganization from "./org/JoinOrganization";
import OrgAssistant from "./org/OrgAssistant";
import OrgDashboard from "./org/OrgDashboard";
import { orgSharingNotice } from "../lib/orgConsent";
import { fetchMyAccessLog, type AccessEntry } from "../lib/orgApi";
import { leaveOrganization, setProgressSharing, type LearnerSummary, type Membership } from "../lib/learnerApi";
import "./org/Org.css";

interface Props {
  summary: LearnerSummary;
  onSummaryChange: (summary: LearnerSummary) => void;
  onBack: () => void;
  onToast: (message: string) => void;
}

/** A learner's own membership: their organization, class, what it can see,
 * and who in it has looked at their details. */
function MemberCard({ membership, onMembership, onToast }: {
  membership: Membership; onMembership: (m: Membership | null) => void; onToast: (m: string) => void;
}) {
  const org = membership.organization;
  const [log, setLog] = useState<AccessEntry[] | null>(null);
  const classLine = [membership.department, membership.year, membership.section].filter(Boolean).join(" · ");

  useEffect(() => { fetchMyAccessLog().then(setLog).catch(() => setLog([])); }, []);

  async function agree() {
    try {
      onMembership(await setProgressSharing(true));
    } catch (err) {
      onToast((err as Error).message);
    }
  }

  async function leave() {
    if (!window.confirm(`Leave ${org.name}? It will stop seeing your progress.`)) return;
    try {
      await leaveOrganization();
      onMembership(null);
      onToast("You left the organization.");
    } catch (err) {
      onToast((err as Error).message);
    }
  }

  return (
    <div className="org-member">
      <section className="org-card org-member-card">
        <span className="org-avatar xl" aria-hidden="true">{org.name.slice(0, 1).toUpperCase()}</span>
        <div>
          <span className="rd-kicker">Your organization</span>
          <h1>{org.name}</h1>
          {classLine && <span className="org-chip">{classLine}</span>}
          {membership.progress_shared ? (
            <p className="rd-muted">{orgSharingNotice(org.name)}</p>
          ) : (
            <>
              <p className="rd-muted">You joined before membership meant sharing, so only your name is visible. {orgSharingNotice(org.name)}</p>
              <button type="button" className="btn btn-outline btn-sm" onClick={() => void agree()}>Agree and share</button>
            </>
          )}
        </div>
      </section>
      <section className="org-card">
        <div className="org-card-head"><h3>Who viewed your details</h3><span className="rd-muted">from {org.name}</span></div>
        {log === null ? <div className="org-skeleton" /> : log.length === 0 ? <p className="rd-muted">No one has opened your details or chats yet.</p> : (
          <ul className="org-history">
            {log.slice(0, 20).map((entry, i) => (
              <li key={i}>
                <span>{entry.at ? new Date(`${entry.at}Z`).toLocaleString() : ""}</span>
                <span><b>{entry.viewer}</b> opened {entry.action === "conversation" ? `your chat "${entry.target}"` : "your details"}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
      <p className="og-leave"><button type="button" className="link-btn" onClick={() => void leave()}>Leave {org.name}</button></p>
    </div>
  );
}

export default function OrganizationView({ summary, onSummaryChange, onBack, onToast }: Props) {
  const membership = summary.membership;
  const setMembership = (next: Membership | null) => onSummaryChange({ ...summary, membership: next });
  const isAdmin = membership && membership.role !== "member";

  return (
    <div className="pv-page rd-page org-page">
      <div className="pv-inner og-inner">
        <button className="hp-back" onClick={onBack}>← Back</button>
        {!membership && <JoinOrganization onJoined={setMembership} onToast={onToast} />}
        {membership && isAdmin && (
          <OrgDashboard org={{ id: membership.organization.id, name: membership.organization.name, kind: membership.organization.kind,
            role: membership.role === "owner" ? "owner" : "admin" }} onToast={onToast}
            extraTabs={[{ name: "Assistant", render: (filters) => (
              <OrgAssistant orgId={membership.organization.id} orgName={membership.organization.name} filters={filters} onToast={onToast} />
            ) }]} />
        )}
        {membership && !isAdmin && <MemberCard membership={membership} onMembership={setMembership} onToast={onToast} />}
      </div>
    </div>
  );
}
