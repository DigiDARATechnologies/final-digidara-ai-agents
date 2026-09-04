import { useEffect, useState } from "react";
import type { User } from "../types";
import { fetchAllUsageSummaries, type AgentUsageResult } from "../lib/usageApi";

interface ProfilePageProps {
  open: boolean;
  user: User;
  onClose: () => void;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export default function ProfilePage({ open, user, onClose }: ProfilePageProps) {
  const [usage, setUsage] = useState<AgentUsageResult[] | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    let active = true;
    setLoading(true);
    fetchAllUsageSummaries().then((results) => {
      if (active) {
        setUsage(results);
        setLoading(false);
      }
    });
    return () => {
      active = false;
    };
  }, [open]);

  const totalTokens = usage?.reduce((sum, a) => sum + (a.usage?.total_tokens ?? 0), 0) ?? 0;
  const totalRequests = usage?.reduce((sum, a) => sum + (a.usage?.total_requests ?? 0), 0) ?? 0;
  const monthlyLimit = 1_000_000;
  const usagePercent = Math.min(100, Math.round((totalTokens / monthlyLimit) * 100));

  return (
    <div
      className={`modal-overlay${open ? " open" : ""}`}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-card modal-card-wide">
        <div className="modal-head">
          <h3>Profile</h3>
          <button className="icon-btn" onClick={onClose}>
            ✕
          </button>
        </div>
        <div className="modal-body">
          <div className="profile-avatar-row">
            <span className="avatar profile-avatar">{user.initial}</span>
            <div>
              <b>{user.name}</b>
              <br />
              <span className="muted">{user.email}</span>
            </div>
          </div>
          <div className="setting-row">
            <div>
              <b>Mobile</b>
              <br />
              <span className="muted">{user.mobile || "Not set"}</span>
            </div>
          </div>
          <div className="setting-row">
            <div>
              <b>Account ID</b>
              <br />
              <span className="muted mono">{user.id}</span>
            </div>
          </div>

          <h4 className="profile-section-head">Agents &amp; token usage</h4>
          {loading && !usage && <p className="muted profile-usage-loading">Loading agent status…</p>}
          {usage && (
            <>
              <div className="profile-usage-total">
                <span>Platform total</span>
                <strong>{formatTokens(totalTokens)} tokens</strong>
                <span className="muted">· {totalRequests} requests</span>
              </div>
              <div className="profile-usage-limit">
                <div><b>Monthly usage</b><span>{Math.max(0, 100 - usagePercent)}% remaining</span></div>
                <div className="usage-progress"><span style={{ width: `${usagePercent}%` }} /></div>
                <small>{formatTokens(totalTokens)} of {formatTokens(monthlyLimit)} tokens used</small>
              </div>
              <div className="profile-agent-list">
                {usage.map((a) => (
                  <div className="profile-agent-row" key={a.id}>
                    <span className="profile-agent-icon" style={{ background: a.color }}>{a.icon}</span>
                    <div className="profile-agent-info">
                      <div className="profile-agent-name">
                        {a.label}
                        <span className={`profile-agent-dot${a.online ? "" : " offline"}`} title={a.online ? "Online" : "Offline"} />
                      </div>
                      <div className="muted profile-agent-stats">
                        {a.usage
                          ? `${formatTokens(a.usage.total_tokens)} tokens · ${a.usage.total_requests} requests`
                          : "Not reachable"}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
