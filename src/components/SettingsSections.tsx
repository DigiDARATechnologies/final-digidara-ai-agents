import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import type { Chat, User } from "../types";
import { LIVE_AGENTS, findAgentByBackendName } from "../data/agents";
import {
  disableTwoStep, enableTwoStep, fetchSignIns, fetchTwoStep, fetchUsageRange, revokeSignIn, signOutOtherDevices,
  startTwoStep, updateProfile, type AccountPrefs, type AccountPrefsPatch, type DateFormat, type SignIn,
  type TwoStepStatus, type UsageRange,
} from "../lib/accountApi";
import { allTimeZones, deviceTimeZone, formatDate, formatDateTime, isoDay } from "../lib/dateFormat";
import { normalizeMobile } from "../lib/profilePrefs";
import { formatPoints } from "../lib/points";
import { TEXT_SIZES, type AppearancePrefs } from "../lib/appearance";
import { SHORTCUTS } from "../lib/shortcuts";

type OnPrefs = (patch: AccountPrefsPatch) => Promise<void>;

function Toggle({ checked, onChange, label, disabled }: { checked: boolean; onChange: (next: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <label className="switch">
      <input type="checkbox" aria-label={label} checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />
      <span className="slider" />
    </label>
  );
}

function Row({ title, children, hint, stack }: { title: string; hint?: ReactNode; children?: ReactNode; stack?: boolean }) {
  return (
    <div className={`setting-row${stack ? " set-stack" : ""}`}>
      <div><b>{title}</b>{hint && <p>{hint}</p>}</div>
      {children}
    </div>
  );
}

/** A row of choices where exactly one is picked. */
export function Segmented<T extends string>({ value, options, onChange, label }: { value: T; options: { id: T; label: string }[]; onChange: (next: T) => void; label: string }) {
  return (
    <div className="set-segmented" role="radiogroup" aria-label={label}>
      {options.map((option) => (
        <button key={option.id} type="button" role="radio" aria-checked={value === option.id} className={value === option.id ? "active" : ""} onClick={() => onChange(option.id)}>
          {option.label}
        </button>
      ))}
    </div>
  );
}

/** Saves a preference and tells the learner if the server refused it. */
function useSave(onPrefs: OnPrefs, onToast: (message: string) => void) {
  return (patch: AccountPrefsPatch) => onPrefs(patch).catch((error: Error) => onToast(error.message || "Could not save that setting."));
}

// --- General -----------------------------------------------------------------------

interface GeneralProps {
  user: User;
  prefs: AccountPrefs;
  onPrefs: OnPrefs;
  onToast: (message: string) => void;
  onProfileSaved: (name: string, mobile: string) => void;
}

const DATE_FORMATS: { id: DateFormat; label: string }[] = [
  { id: "auto", label: "Automatic (device)" },
  { id: "dmy", label: "DD/MM/YYYY" },
  { id: "mdy", label: "MM/DD/YYYY" },
  { id: "ymd", label: "YYYY-MM-DD" },
];

export function GeneralPreferences({ user, prefs, onPrefs, onToast, onProfileSaved }: GeneralProps) {
  const save = useSave(onPrefs, onToast);
  const [name, setName] = useState(user.name);
  const [mobile, setMobile] = useState(user.mobile || "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { setName(user.name); setMobile(user.mobile || ""); }, [user.name, user.mobile]);
  const zones = useMemo(() => allTimeZones(), []);
  const changed = name.trim() !== user.name || mobile.trim() !== (user.mobile || "");

  async function saveProfile(event: FormEvent) {
    event.preventDefault();
    setError("");
    const trimmed = name.trim();
    if (!trimmed) return setError("Please enter your name.");
    const cleanMobile = mobile.trim() ? normalizeMobile(mobile) : "";
    if (cleanMobile === null) return setError("Please enter a valid mobile number, like +91 98765 43210.");
    setBusy(true);
    try {
      const saved = await updateProfile(trimmed, cleanMobile);
      onProfileSaved(saved.name, saved.mobile || "");
      onToast("Profile saved.");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h3 className="settings-title">Profile</h3>
      <form className="set-form" onSubmit={saveProfile}>
        <label className="field"><span>Full Name</span><input value={name} maxLength={255} autoComplete="name" onChange={(event) => setName(event.target.value)} /></label>
        <label className="field"><span>Mobile Number</span><input value={mobile} maxLength={32} inputMode="tel" autoComplete="tel" placeholder="+91 98765 43210" onChange={(event) => setMobile(event.target.value)} /></label>
        <label className="field"><span>Email</span><input value={user.email} disabled readOnly /></label>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button type="submit" className="btn btn-primary" disabled={busy || !changed}>{busy ? "Saving…" : "Save Profile"}</button>
      </form>

      <h3 className="settings-title">Preferences</h3>
      <div className="settings-section">
        <Row title="Language" hint="SkillDARA agents understand and reply in English only, so the app is in English." >
          <span className="set-value">English</span>
        </Row>
        <Row title="Open After Signing In" hint="The agent that opens when you sign in. Home shows every agent.">
          <select className="set-select" aria-label="Open after signing in" value={prefs.general.default_agent} onChange={(event) => void save({ general: { default_agent: event.target.value } })}>
            <option value="">Home</option>
            {LIVE_AGENTS.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}
          </select>
        </Row>
        <Row title="Time Zone" hint="Used for every date and time in the app.">
          <select className="set-select" aria-label="Time zone" value={prefs.general.time_zone} onChange={(event) => void save({ general: { time_zone: event.target.value } })}>
            <option value="">Device ({deviceTimeZone()})</option>
            {zones.map((zone) => <option key={zone} value={zone}>{zone.replace(/_/g, " ")}</option>)}
          </select>
        </Row>
        <Row title="Date Format" hint={`Today shows as ${formatDate(Date.now())}.`}>
          <select className="set-select" aria-label="Date format" value={prefs.general.date_format} onChange={(event) => void save({ general: { date_format: event.target.value as DateFormat } })}>
            {DATE_FORMATS.map((format) => <option key={format.id} value={format.id}>{format.label}</option>)}
          </select>
        </Row>
      </div>
    </>
  );
}

// --- Notifications -------------------------------------------------------------------

export function NotificationSettings({ prefs, onPrefs, onToast }: { prefs: AccountPrefs; onPrefs: OnPrefs; onToast: (message: string) => void }) {
  const save = useSave(onPrefs, onToast);
  const n = prefs.notifications;
  const set = (key: keyof AccountPrefs["notifications"]) => (value: boolean) => void save({ notifications: { [key]: value } });
  return (
    <>
      <h2>Notifications</h2>
      <p className="settings-subtitle">Choose what SkillDARA tells you about, and how.</p>
      <h3 className="settings-title">In the App</h3>
      <div className="settings-section">
        <Row title="In-App Alerts" hint="The bell in the top bar: work waiting in an agent, a project deadline, a viva ready to start.">
          <Toggle label="In-app alerts" checked={n.in_app} onChange={set("in_app")} />
        </Row>
        <Row title="Low Coin Warning" hint="A reminder to top up when your coins are running low: here in the app, and by email at most once a month when emails are on.">
          <Toggle label="Low coin warning" checked={n.low_coin_warning} onChange={set("low_coin_warning")} />
        </Row>
      </div>
      <h3 className="settings-title">By Email</h3>
      <div className="settings-section">
        <Row title="Email Notifications" hint="Turn this off to stop every email below. Sign-in codes and receipts still arrive.">
          <Toggle label="Email notifications" checked={n.email} onChange={set("email")} />
        </Row>
        <Row title="Assessment Reminders" hint="When an assessment from your college or company closes within a day and you haven't started it.">
          <Toggle label="Assessment reminders" checked={n.assessment_reminders} disabled={!n.email} onChange={set("assessment_reminders")} />
        </Row>
        <Row title="Weekly Progress Email" hint="Every Monday morning: what you practised last week, agent by agent.">
          <Toggle label="Weekly progress email" checked={n.weekly_progress} disabled={!n.email} onChange={set("weekly_progress")} />
        </Row>
      </div>
    </>
  );
}

// --- Accessibility -------------------------------------------------------------------

export function AccessibilitySettings({ appearance, onAppearanceChange }: { appearance: AppearancePrefs; onAppearanceChange: (next: AppearancePrefs) => void }) {
  const set = <K extends keyof AppearancePrefs>(key: K, value: AppearancePrefs[K]) => onAppearanceChange({ ...appearance, [key]: value });
  return (
    <>
      <h2>Accessibility</h2>
      <p className="settings-subtitle">Make SkillDARA easier to see, hear and use. Remembered on this device.</p>
      <div className="settings-section">
        <Row title="Text Size" hint="Makes all text in the app bigger or smaller." stack>
          <Segmented label="Text size" value={appearance.textSize} options={TEXT_SIZES} onChange={(value) => set("textSize", value)} />
        </Row>
        <Row title="High Contrast" hint="Darker text, stronger borders and clearer focus outlines.">
          <Toggle label="High contrast" checked={appearance.highContrast} onChange={(value) => set("highContrast", value)} />
        </Row>
        <Row title="Reduce Motion" hint="Turns off moving effects such as the scrolling agent strip.">
          <Toggle label="Reduce motion" checked={appearance.reduceMotion} onChange={(value) => set("reduceMotion", value)} />
        </Row>
        <Row title="Captions for Voice" hint="In a voice conversation with Boss, show what Boss says and what it heard you say.">
          <Toggle label="Captions for voice" checked={appearance.captions} onChange={(value) => set("captions", value)} />
        </Row>
        <Row title="Keyboard Shortcuts" hint="Turn off if the shortcuts get in the way of your screen reader or keyboard tools.">
          <Toggle label="Keyboard shortcuts" checked={appearance.shortcuts} onChange={(value) => set("shortcuts", value)} />
        </Row>
      </div>
      <h3 className="settings-title" id="settings-shortcuts">Shortcuts</h3>
      <dl className={`set-shortcuts${appearance.shortcuts ? "" : " off"}`}>
        {SHORTCUTS.map((shortcut) => (
          <div key={shortcut.label}><dt>{shortcut.label}</dt><dd>{shortcut.keys.split(" + ").map((key) => <kbd key={key}>{key}</kbd>)}</dd></div>
        ))}
      </dl>
    </>
  );
}

// --- Security: devices, login history and two-step ------------------------------------------

const METHOD_LABEL: Record<SignIn["method"], string> = { password: "Password", google: "Google", signup: "New account", two_step: "Password + code" };

export function SignInSettings({ onToast, onLogout }: { onToast: (message: string) => void; onLogout?: () => void }) {
  const [rows, setRows] = useState<SignIn[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const load = () => fetchSignIns().then((list) => { setRows(list); setError(""); }).catch((err: Error) => setError(err.message));
  useEffect(() => { void load(); }, []);

  async function signOut(row: SignIn) {
    if (row.current) { onLogout?.(); return; }
    setBusy(row.id);
    try { await revokeSignIn(row.id); onToast(`Signed out ${row.device}.`); await load(); }
    catch (err) { onToast((err as Error).message); }
    finally { setBusy(null); }
  }

  async function signOutOthers() {
    setBusy("others");
    try { await signOutOtherDevices(); onToast("Signed out of every other device."); await load(); }
    catch (err) { onToast((err as Error).message); }
    finally { setBusy(null); }
  }

  const active = rows?.filter((row) => row.active) ?? [];
  return (
    <>
      <h3 className="settings-title">Devices Signed In</h3>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="settings-section set-device-list">
        {rows === null && !error && <p className="set-muted">Loading…</p>}
        {active.map((row) => (
          <div className="setting-row" key={row.id}>
            <div>
              <b>{row.device}{row.current && <span className="set-chip">This device</span>}</b>
              <p>Signed in {formatDateTime(row.created_at)} · {METHOD_LABEL[row.method]}{row.ip ? ` · ${row.ip}` : ""}</p>
            </div>
            <button type="button" className="btn btn-outline" disabled={busy === row.id} onClick={() => void signOut(row)}>{row.current ? "Log Out" : "Sign Out"}</button>
          </div>
        ))}
        {rows !== null && active.length === 0 && <p className="set-muted">Only this device. Sign-ins from before this list existed aren't shown.</p>}
      </div>
      <button type="button" className="btn btn-outline btn-danger set-gap" disabled={busy === "others"} onClick={() => void signOutOthers()}>
        {busy === "others" ? "Signing out…" : "Sign Out of All Other Devices"}
      </button>

      <h3 className="settings-title">Login History</h3>
      <p className="settings-subtitle set-tight">Every sign-in to your account, newest first. If you don't recognise one, change your password.</p>
      <div className="set-history">
        {rows?.map((row) => (
          <div key={row.id}>
            <span><b>{row.device}</b><small>{METHOD_LABEL[row.method]}{row.ip ? ` · ${row.ip}` : ""}</small></span>
            <span><b>{formatDateTime(row.created_at)}</b><small className={row.active ? "ok" : ""}>{row.active ? "Signed in" : row.revoked_at ? "Signed out" : "Ended"}</small></span>
          </div>
        ))}
        {rows?.length === 0 && <p className="set-muted">No sign-ins recorded yet.</p>}
      </div>
    </>
  );
}

export function TwoStepSettings({ onToast }: { onToast: (message: string) => void }) {
  const [status, setStatus] = useState<TwoStepStatus | null>(null);
  const [step, setStep] = useState<"idle" | "password" | "code" | "disable">("idle");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { fetchTwoStep().then(setStatus).catch(() => setStatus(null)); }, []);

  function reset() { setStep("idle"); setPassword(""); setCode(""); setError(""); setMessage(""); }

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try { await action(); } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }

  if (!status) return null;
  const blocked = !status.password_account ? "You sign in with Google, which already checks it's you. Two-step verification protects password sign-ins."
    : !status.available ? "Two-step verification needs email, which isn't available on this server right now." : "";

  return (
    <>
      <h3 className="settings-title">Two-Step Verification</h3>
      <div className="settings-section">
        <Row title={status.enabled ? "On" : "Off"} hint={blocked || `When it's on, signing in with your password also needs a 6-digit code we email to ${status.email}.`}>
          {!blocked && step === "idle" && (status.enabled
            ? <button type="button" className="btn btn-outline btn-danger" onClick={() => setStep("disable")}>Turn Off</button>
            : <button type="button" className="btn btn-primary" onClick={() => setStep("password")}>Turn On</button>)}
        </Row>
      </div>
      {step === "password" && (
        <form className="set-form" onSubmit={(event) => { event.preventDefault(); void run(async () => { const result = await startTwoStep(password); setMessage(result.message); setStep("code"); }); }}>
          <label className="field"><span>Confirm Your Password</span><input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="set-actions"><button type="submit" className="btn btn-primary" disabled={busy || !password}>{busy ? "Sending…" : "Send Code"}</button><button type="button" className="btn btn-outline" onClick={reset}>Cancel</button></div>
        </form>
      )}
      {step === "code" && (
        <form className="set-form" onSubmit={(event) => { event.preventDefault(); void run(async () => { await enableTwoStep(code); setStatus({ ...status, enabled: true }); reset(); onToast("Two-step verification is on."); }); }}>
          <p className="set-muted">{message}</p>
          <label className="field"><span>6-Digit Code</span><input inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} /></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="set-actions"><button type="submit" className="btn btn-primary" disabled={busy || code.length !== 6}>{busy ? "Checking…" : "Turn On"}</button><button type="button" className="btn btn-outline" onClick={reset}>Cancel</button></div>
        </form>
      )}
      {step === "disable" && (
        <form className="set-form" onSubmit={(event) => { event.preventDefault(); void run(async () => { await disableTwoStep(password); setStatus({ ...status, enabled: false }); reset(); onToast("Two-step verification is off."); }); }}>
          <label className="field"><span>Confirm Your Password</span><input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="set-actions"><button type="submit" className="btn btn-outline btn-danger" disabled={busy || !password}>{busy ? "Turning off…" : "Turn Off"}</button><button type="button" className="btn btn-outline" onClick={reset}>Cancel</button></div>
        </form>
      )}
    </>
  );
}

// --- Billing ---------------------------------------------------------------------------

export function BillingPreferences({ prefs, onPrefs, onToast, accountEmail }: { prefs: AccountPrefs; onPrefs: OnPrefs; onToast: (message: string) => void; accountEmail: string }) {
  const save = useSave(onPrefs, onToast);
  const [email, setEmail] = useState(prefs.billing.billing_email);
  useEffect(() => setEmail(prefs.billing.billing_email), [prefs.billing.billing_email]);
  const valid = email.trim() === "" || /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(email.trim());
  return (
    <>
      <h3 className="settings-title">Billing Preferences</h3>
      <div className="settings-section">
        <Row title="Billing Email" hint={`Plan reminders go here. Leave empty to use ${accountEmail}. Invoices are below, under Transaction History.`} stack>
          <form className="set-inline" onSubmit={(event) => { event.preventDefault(); if (valid) void save({ billing: { billing_email: email.trim() } }).then(() => onToast("Billing email saved.")); }}>
            <input type="email" value={email} placeholder={accountEmail} aria-label="Billing email" aria-invalid={!valid} onChange={(event) => setEmail(event.target.value)} />
            <button type="submit" className="btn btn-outline" disabled={!valid || email.trim() === prefs.billing.billing_email}>Save</button>
          </form>
        </Row>
        <Row title="Plan Renewal Reminder" hint="Plans are one-time payments and never charge you again on their own. We email you 3 days before your plan ends, so you can buy it again if you want to.">
          <Toggle label="Plan renewal reminder" checked={prefs.billing.renewal_reminder} onChange={(value) => void save({ billing: { renewal_reminder: value } })} />
        </Row>
      </div>
    </>
  );
}

// --- Usage -------------------------------------------------------------------------------

const WARN_OPTIONS = [0, 50, 75, 80, 90];

function agentLabel(name: string): string {
  return findAgentByBackendName(name)?.name ?? (name || "Other").replace(/[_-]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function csvCell(value: string | number): string {
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function downloadFile(filename: string, content: string, type: string): void {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function usageCsv(data: UsageRange): string {
  const lines = [["Date", "Time", "Agent", "Action", "Coins"].join(",")];
  for (const event of data.events) {
    lines.push([formatDate(event.at), new Date(event.at).toLocaleTimeString(), agentLabel(event.agent_name), event.action, event.points].map(csvCell).join(","));
  }
  return lines.join("\n");
}

export function UsageTools({ prefs, onPrefs, onToast }: { prefs: AccountPrefs; onPrefs: OnPrefs; onToast: (message: string) => void }) {
  const save = useSave(onPrefs, onToast);
  const today = isoDay(Date.now());
  const [start, setStart] = useState(isoDay(Date.now() - 29 * 86_400_000));
  const [end, setEnd] = useState(today);
  const [data, setData] = useState<UsageRange | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load(from = start, to = end) {
    setLoading(true);
    setError("");
    try { setData(await fetchUsageRange(from, to)); } catch (err) { setError((err as Error).message); setData(null); } finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);

  function preset(days: number | "month") {
    const now = new Date();
    const from = days === "month" ? isoDay(new Date(now.getFullYear(), now.getMonth(), 1)) : isoDay(Date.now() - (days - 1) * 86_400_000);
    setStart(from);
    setEnd(today);
    void load(from, today);
  }

  const maxDay = Math.max(1, ...(data?.days.map((day) => day.points) ?? [1]));
  return (
    <>
      <h3 className="settings-title">Usage Warning</h3>
      <div className="settings-section">
        <Row title="Warn Me At" hint="Shows a warning once a month when you've used this much of the month's coins.">
          <select className="set-select" aria-label="Usage warning" value={prefs.usage.warn_percent} onChange={(event) => void save({ usage: { warn_percent: Number(event.target.value) } })}>
            {WARN_OPTIONS.map((value) => <option key={value} value={value}>{value === 0 ? "Off" : `${value}% used`}</option>)}
          </select>
        </Row>
      </div>

      <h3 className="settings-title">Usage by Date</h3>
      <div className="set-range">
        <label><span>From</span><input type="date" value={start} max={end} onChange={(event) => setStart(event.target.value)} /></label>
        <label><span>To</span><input type="date" value={end} min={start} max={today} onChange={(event) => setEnd(event.target.value)} /></label>
        <button type="button" className="btn btn-primary" disabled={loading || !start || !end} onClick={() => void load()}>{loading ? "Loading…" : "Show"}</button>
        <div className="set-presets">
          <button type="button" onClick={() => preset(7)}>Last 7 days</button>
          <button type="button" onClick={() => preset(30)}>Last 30 days</button>
          <button type="button" onClick={() => preset("month")}>This month</button>
        </div>
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      {data && (
        <>
          <div className="settings-platform-total set-gap">
            <span>{formatDate(`${data.start}T12:00:00`)} – {formatDate(`${data.end}T12:00:00`)}</span>
            <strong>{formatPoints(data.points_used)} coins</strong>
            <small>· {data.requests} requests</small>
            <button type="button" className="btn btn-outline set-push" disabled={!data.events.length}
              onClick={() => downloadFile(`skilldara-usage-${data.start}-to-${data.end}.csv`, usageCsv(data), "text/csv;charset=utf-8")}>Export CSV</button>
          </div>
          {data.days.length > 0 && (
            <div className="set-bars" role="img" aria-label="Coins used per day">
              {data.days.map((day) => (
                <span key={day.day} title={`${formatDate(`${day.day}T12:00:00`)}: ${formatPoints(day.points)} coins, ${day.requests} requests`} style={{ height: `${Math.max(4, (day.points / maxDay) * 100)}%` }} />
              ))}
            </div>
          )}
          <div className="usage-settings-list">
            {data.agents.map((row) => (
              <div key={row.agent_name}><span /><span><b>{agentLabel(row.agent_name)}</b><small>{formatPoints(row.points)} coins · {row.requests} requests</small></span></div>
            ))}
            {!data.agents.length && <p className="set-muted">No usage in these dates.</p>}
          </div>
        </>
      )}
    </>
  );
}

// --- Agent chats: export -------------------------------------------------------------------

/** One agent's chats as a Markdown document, oldest message first in each chat. */
export function agentChatsMarkdown(agentName: string, chats: Chat[]): string {
  const lines = [`# ${agentName} — chats`, "", `Exported ${formatDateTime(Date.now())}. ${chats.length} chat${chats.length === 1 ? "" : "s"}.`, ""];
  for (const chat of chats) {
    lines.push(`## ${chat.title}`, "", `_Last updated ${formatDateTime(chat.updatedAt)}_`, "");
    for (const message of chat.messages) {
      const who = message.role === "user" ? "You" : agentName;
      lines.push(`**${who}**${message.time ? ` (${message.time})` : ""}:`, "", (message.text || "").trim() || "_(no text)_", "");
    }
  }
  return lines.join("\n");
}
