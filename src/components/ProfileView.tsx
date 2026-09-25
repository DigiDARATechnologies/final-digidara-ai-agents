import { useEffect, useMemo, useState } from "react";
import type { Chat, User } from "../types";
import { AGENTS, DEFAULT_AGENT, findAgent } from "../data/agents";
import { fetchAllUsageSummaries } from "../lib/usageApi";
import EditProfileModal from "./EditProfileModal";
import type { ProfilePrefs } from "../lib/profilePrefs";

interface Props {
  user: User;
  chats: Chat[];
  planName: string;
  onBack: () => void;
  onUpgrade: () => void;
  prefs: ProfilePrefs;
  onSaveProfile: (prefs: ProfilePrefs) => void;
}

type Range = "daily" | "weekly" | "cumulative";

const WEEKS = 53;
const DAY_MS = 86_400_000;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function dayKey(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function startOfDay(ts: number) {
  const d = new Date(ts);
  d.setHours(0, 0, 0, 0);
  return d;
}

function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function plural(n: number, word: string) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

export default function ProfileView({ user, chats, planName, onBack, onUpgrade, prefs, onSaveProfile }: Props) {
  const [editing, setEditing] = useState(false);
  const [range, setRange] = useState<Range>("daily");
  const [lifetimeTokens, setLifetimeTokens] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    fetchAllUsageSummaries()
      .then((results) => {
        if (active) setLifetimeTokens(results.reduce((sum, a) => sum + (a.usage?.total_tokens ?? 0), 0));
      })
      .catch(() => {
        if (active) setLifetimeTokens(null);
      });
    return () => {
      active = false;
    };
  }, []);

  const stats = useMemo(() => {
    const perDay = new Map<string, number>();
    let totalMessages = 0;
    const perAgent = new Map<string, { chats: number; messages: number }>();

    for (const chat of chats) {
      const userMessages = chat.messages.filter((m) => m.role === "user").length;
      totalMessages += userMessages;
      const key = dayKey(startOfDay(chat.updatedAt));
      perDay.set(key, (perDay.get(key) ?? 0) + Math.max(userMessages, 0));
      const entry = perAgent.get(chat.agentId) ?? { chats: 0, messages: 0 };
      entry.chats += 1;
      entry.messages += userMessages;
      perAgent.set(chat.agentId, entry);
    }

    const today = startOfDay(Date.now());
    const activeKeys = new Set([...perDay.entries()].filter(([, v]) => v > 0).map(([k]) => k));

    let current = 0;
    const cursor = new Date(today);
    if (!activeKeys.has(dayKey(cursor))) cursor.setDate(cursor.getDate() - 1);
    while (activeKeys.has(dayKey(cursor))) {
      current += 1;
      cursor.setDate(cursor.getDate() - 1);
    }

    const sorted = [...activeKeys].sort();
    let longest = 0;
    let run = 0;
    let prev: number | null = null;
    for (const k of sorted) {
      const [y, m, d] = k.split("-").map(Number);
      const t = new Date(y, m - 1, d).getTime();
      run = prev !== null && Math.round((t - prev) / DAY_MS) === 1 ? run + 1 : 1;
      longest = Math.max(longest, run);
      prev = t;
    }

    let busiest: { key: string; value: number } | null = null;
    for (const [key, value] of perDay) if (value > 0 && (!busiest || value > busiest.value)) busiest = { key, value };

    const topAgents = [...perAgent.entries()]
      .map(([agentId, v]) => ({ agent: findAgent(agentId) ?? DEFAULT_AGENT, ...v }))
      .sort((a, b) => b.messages - a.messages || b.chats - a.chats)
      .slice(0, 5);

    // grid: WEEKS columns, Sunday-first, ending with the current week
    const gridStart = new Date(today);
    gridStart.setDate(gridStart.getDate() - gridStart.getDay() - (WEEKS - 1) * 7);
    const cells: { key: string; date: Date; value: number; future: boolean }[] = [];
    for (let i = 0; i < WEEKS * 7; i += 1) {
      const date = new Date(gridStart);
      date.setDate(gridStart.getDate() + i);
      const key = dayKey(date);
      cells.push({ key, date, value: perDay.get(key) ?? 0, future: date.getTime() > today.getTime() });
    }
    const weekly = Array.from({ length: WEEKS }, (_, w) => cells.slice(w * 7, w * 7 + 7).reduce((s, c) => s + c.value, 0));
    let running = 0;
    const cumulative = weekly.map((v) => (running += v));
    const max = Math.max(1, ...cells.map((c) => c.value));

    const monthLabels: { col: number; label: string }[] = [];
    let lastMonth = -1;
    let lastCol = -10;
    for (let w = 0; w < WEEKS; w += 1) {
      const m = cells[w * 7].date.getMonth();
      if (m !== lastMonth && w - lastCol >= 3) {
        monthLabels.push({ col: w, label: MONTHS[m] });
        lastCol = w;
      }
      lastMonth = m;
    }

    return { totalMessages, current, longest, busiest, topAgents, cells, weekly, cumulative, max, monthLabels, activeDays: activeKeys.size, totalChats: chats.length };
  }, [chats]);

  const handle = prefs.username || user.email.split("@")[0];
  const level = (v: number) => (v <= 0 ? 0 : Math.min(4, Math.ceil((v / stats.max) * 4)));
  const weeklyMax = Math.max(1, ...stats.weekly);
  const cumMax = Math.max(1, ...stats.cumulative);
  const topMax = Math.max(1, ...stats.topAgents.map((a) => a.messages));

  const busiestLabel = stats.busiest
    ? (() => {
        const [y, m, d] = stats.busiest.key.split("-").map(Number);
        return `${MONTHS[m - 1]} ${d}, ${y} (${plural(stats.busiest.value, "message")})`;
      })()
    : "None yet";

  return (
    <div className="pv-page">
      <div className="pv-inner">
        <button type="button" className="hp-back" onClick={onBack}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M15 6l-6 6 6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Back
        </button>

        <button type="button" className="pv-edit" onClick={() => setEditing(true)}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M4 20l1.2-4.2L16.5 4.5a2 2 0 012.8 0l.2.2a2 2 0 010 2.8L8.2 18.8 4 20z" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Edit
        </button>

        <header className="pv-head">
          <span className="pv-avatar">{user.avatarUrl ? <img src={user.avatarUrl} alt="Your profile" /> : user.initial}</span>
          <h1>{user.name}</h1>
          <div className="pv-handle">
            <span>@{handle}</span>
            <span className="pv-dot">·</span>
            <button type="button" className={`plan-badge${planName === "Free" ? " free" : ""}`} onClick={onUpgrade} title="View plans">
              {planName}
            </button>
          </div>
        </header>

        <div className="pv-stats">
          <div>
            <b>{lifetimeTokens === null ? "—" : formatCount(lifetimeTokens)}</b>
            <span>Lifetime tokens</span>
          </div>
          <div>
            <b>{stats.totalChats}</b>
            <span>Total chats</span>
          </div>
          <div>
            <b>{plural(stats.current, "day")}</b>
            <span>Current streak</span>
          </div>
          <div>
            <b>{plural(stats.longest, "day")}</b>
            <span>Longest streak</span>
          </div>
        </div>

        <section className="pv-section">
          <div className="pv-section-head">
            <h2>Chat activity</h2>
            <div className="pv-range" role="tablist">
              {(["daily", "weekly", "cumulative"] as Range[]).map((r) => (
                <button key={r} type="button" className={range === r ? "active" : ""} onClick={() => setRange(r)}>
                  {r[0].toUpperCase() + r.slice(1)}
                </button>
              ))}
            </div>
          </div>

          <div className="pv-chart">
            {range === "daily" && (
              <div className="pv-heat-wrap">
                <div className="pv-heat">
                  {stats.cells.map((c) => (
                    <span
                      key={c.key}
                      className={`pv-cell l${level(c.value)}${c.future ? " future" : ""}`}
                      title={`${plural(c.value, "message")} on ${MONTHS[c.date.getMonth()]} ${c.date.getDate()}, ${c.date.getFullYear()}`}
                    />
                  ))}
                </div>
                <div className="pv-months">
                  {stats.monthLabels.map((m) => (
                    <span key={`${m.label}-${m.col}`} style={{ gridColumn: `${m.col + 1} / span 3` }}>
                      {m.label}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {range === "weekly" && (
              <div className="pv-bars">
                {stats.weekly.map((v, i) => (
                  <span key={i} title={plural(v, "message")} style={{ height: `${Math.max(3, (v / weeklyMax) * 100)}%` }} className={v ? "on" : ""} />
                ))}
              </div>
            )}
            {range === "cumulative" && (
              <svg className="pv-line" viewBox="0 0 530 120" preserveAspectRatio="none" role="img" aria-label="Cumulative messages">
                <defs>
                  <linearGradient id="pvfill" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stopColor="#4b78ff" stopOpacity=".45" />
                    <stop offset="100%" stopColor="#4b78ff" stopOpacity="0" />
                  </linearGradient>
                </defs>
                <polygon
                  fill="url(#pvfill)"
                  points={`0,120 ${stats.cumulative.map((v, i) => `${(i / (WEEKS - 1)) * 530},${118 - (v / cumMax) * 112}`).join(" ")} 530,120`}
                />
                <polyline
                  fill="none"
                  stroke="#4b78ff"
                  strokeWidth="2"
                  vectorEffect="non-scaling-stroke"
                  points={stats.cumulative.map((v, i) => `${(i / (WEEKS - 1)) * 530},${118 - (v / cumMax) * 112}`).join(" ")}
                />
              </svg>
            )}
          </div>
          <p className="pv-note">Messages you sent, based on the conversations saved on this device.</p>
        </section>

        <div className="pv-two">
          <section className="pv-section">
            <h2>Activity insights</h2>
            <dl className="pv-insights">
              <div><dt>Most used agent</dt><dd>{stats.topAgents[0]?.agent.name ?? "None yet"}</dd></div>
              <div><dt>Messages sent</dt><dd>{stats.totalMessages}</dd></div>
              <div><dt>Active days</dt><dd>{stats.activeDays}</dd></div>
              <div><dt>Busiest day</dt><dd>{busiestLabel}</dd></div>
              <div><dt>Agents available</dt><dd>{AGENTS.length}</dd></div>
              <div><dt>Total chats</dt><dd>{stats.totalChats}</dd></div>
            </dl>
          </section>

          <section className="pv-section">
            <h2>Most used agents</h2>
            {stats.topAgents.length === 0 ? (
              <div className="pv-empty">No agents used yet. Start a chat to see your favourites here.</div>
            ) : (
              <ul className="pv-top">
                {stats.topAgents.map((a) => (
                  <li key={a.agent.id}>
                    <span className="pv-top-icon" style={{ background: `color-mix(in srgb, ${a.agent.color} 28%, transparent)` }}>{a.agent.icon}</span>
                    <div className="pv-top-main">
                      <div className="pv-top-row">
                        <b>{a.agent.name}</b>
                        <span>{plural(a.messages, "message")}</span>
                      </div>
                      <div className="pv-top-bar"><span style={{ width: `${(a.messages / topMax) * 100}%`, background: a.agent.color }} /></div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        <section className="pv-section">
          <h2>Account</h2>
          <dl className="pv-insights">
            <div><dt>Email</dt><dd>{user.email}</dd></div>
            <div><dt>Mobile</dt><dd>{user.mobile || "Not set"}</dd></div>
            <div><dt>Plan</dt><dd>{planName}</dd></div>
            <div><dt>Account ID</dt><dd className="pv-mono">{user.id}</dd></div>
          </dl>
        </section>
      </div>
      {editing && (
        <EditProfileModal
          initialName={user.name}
          initialUsername={handle}
          initialAvatar={user.avatarUrl}
          initial={user.initial}
          onCancel={() => setEditing(false)}
          onSave={(next) => {
            onSaveProfile(next);
            setEditing(false);
          }}
        />
      )}
    </div>
  );
}
