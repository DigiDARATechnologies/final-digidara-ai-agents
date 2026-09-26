import { useMemo, useState, type FormEvent } from "react";
import type { User } from "../types";
import { FAQ, RELEASES, SUPPORT_EMAIL } from "../data/helpContent";
import { AGENTS, CATEGORIES } from "../data/agents";

export type HelpPageKind = "help-center" | "release-notes" | "contact" | "bug-report";

interface Props {
  page: HelpPageKind;
  user: User;
  theme: "dark" | "light";
  onBack: () => void;
  onNavigate: (page: HelpPageKind) => void;
  onToast: (message: string) => void;
}

const TITLES: Record<HelpPageKind, { title: string; sub: string }> = {
  "help-center": { title: "Help center", sub: "Find quick answers, or reach out to our team." },
  "release-notes": { title: "Release notes", sub: "See what's new and improved in DigiDARA Agents." },
  contact: { title: "Contact support", sub: "Tell us what you need and our team will get back to you." },
  "bug-report": { title: "Report a bug", sub: "Something not working? Give us the details and we'll look into it." },
};

function composeUrls(subject: string, body: string) {
  const s = encodeURIComponent(subject);
  const b = encodeURIComponent(body);
  return {
    gmail: `https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(SUPPORT_EMAIL)}&su=${s}&body=${b}`,
    outlook: `https://outlook.office.com/mail/deeplink/compose?to=${encodeURIComponent(SUPPORT_EMAIL)}&subject=${s}&body=${b}`,
  };
}

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

function SendPanel({ subject, body, onToast }: { subject: string; body: string; onToast: (m: string) => void }) {
  const urls = composeUrls(subject, body);
  return (
    <div className="hp-send">
      <p className="hp-send-note">
        Choose how to send this to <b>{SUPPORT_EMAIL}</b>. Your message is filled in for you.
      </p>
      <div className="hp-send-row">
        <a className="btn btn-primary" href={urls.gmail} target="_blank" rel="noopener noreferrer">Send with Gmail</a>
        <a className="btn btn-outline" href={urls.outlook} target="_blank" rel="noopener noreferrer">Send with Outlook</a>
        <button
          type="button"
          className="btn btn-outline"
          onClick={async () => onToast((await copyText(`To: ${SUPPORT_EMAIL}\nSubject: ${subject}\n\n${body}`)) ? "Message copied. Paste it into any email app." : "Could not copy. Please select and copy the text manually.")}
        >
          Copy message
        </button>
      </div>
    </div>
  );
}

function HelpCenter({ onNavigate }: { onNavigate: (p: HelpPageKind) => void }) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string>("All");
  const [openIdx, setOpenIdx] = useState<number | null>(0);
  const q = query.trim().toLowerCase();

  const results = useMemo(() => {
    if (!q) return FAQ;
    return FAQ.filter((f) => f.q.toLowerCase().includes(q) || f.a.toLowerCase().includes(q) || f.topic.toLowerCase().includes(q));
  }, [q]);
  const topics = Array.from(new Set(results.map((f) => f.topic)));

  const agents = useMemo(
    () =>
      AGENTS.filter(
        (a) =>
          (category === "All" || a.category?.includes(category)) &&
          (!q || a.name.toLowerCase().includes(q) || (a.desc ?? "").toLowerCase().includes(q) || (a.category ?? []).join(" ").toLowerCase().includes(q)),
      ),
    [category, q],
  );

  return (
    <>
      <input
        className="hp-search"
        type="search"
        placeholder="Search help and agents…"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpenIdx(null);
        }}
      />

      <section className="hp-group">
        <h3>Meet the agents</h3>
        <p className="hp-lead">
          Each DigiDARA agent is built for a specific job. Pick the one that matches your goal, or open My agents to try any of them.
        </p>
        <div className="hp-chips" role="tablist" aria-label="Filter agents by category">
          {["All", ...CATEGORIES].map((c) => (
            <button key={c} type="button" className={`hp-chip${category === c ? " active" : ""}`} onClick={() => setCategory(c)}>
              {c}
            </button>
          ))}
        </div>
        {agents.length === 0 ? (
          <p className="hp-empty">No agents match your search.</p>
        ) : (
          <div className="hp-agents">
            {agents.map((a) => (
              <div key={a.id} className="hp-agent" style={{ ["--agent-color" as string]: a.color }}>
                <span className="hp-agent-icon">{a.icon}</span>
                <div className="hp-agent-main">
                  <b>{a.name}</b>
                  <p>{a.desc}</p>
                  <div className="hp-agent-tags">
                    {(a.category ?? []).map((c) => (
                      <span key={c}>{c}</span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {results.length === 0 && <p className="hp-empty">No help articles found for “{query}”. Try different words, or contact our team below.</p>}
      {topics.map((topic) => (
        <section key={topic} className="hp-group">
          <h3>{topic}</h3>
          {results
            .filter((f) => f.topic === topic)
            .map((f) => {
              const idx = FAQ.indexOf(f);
              const open = openIdx === idx || (q !== "" && results.length <= 3);
              return (
                <div key={f.q} className={`hp-item${open ? " open" : ""}`}>
                  <button type="button" className="hp-q" aria-expanded={open} onClick={() => setOpenIdx(open ? null : idx)}>
                    <span>{f.q}</span>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </button>
                  {open && <p className="hp-a">{f.a}</p>}
                </div>
              );
            })}
        </section>
      ))}
      <div className="hp-cta">
        <div>
          <b>Still need help?</b>
          <span>Our team is happy to help.</span>
        </div>
        <div className="hp-cta-actions">
          <button type="button" className="btn btn-primary" onClick={() => onNavigate("contact")}>Contact support</button>
          <button type="button" className="btn btn-outline" onClick={() => onNavigate("bug-report")}>Report a bug</button>
        </div>
      </div>
    </>
  );
}

function ReleaseNotes() {
  return (
    <>
      {RELEASES.map((r) => (
        <article key={r.date} className="hp-release">
          <span className="hp-release-date">{r.date}</span>
          <h3>{r.title}</h3>
          <p className="hp-release-summary">{r.summary}</p>
          {r.sections.map((sec) => (
            <div key={sec.label} className="hp-release-sec">
              <span className={`hp-tag hp-tag-${sec.label.toLowerCase()}`}>{sec.label}</span>
              <ul>
                {sec.items.map((i) => (
                  <li key={i}>{i}</li>
                ))}
              </ul>
            </div>
          ))}
        </article>
      ))}
      <p className="hp-release-foot">
        Have an idea or found something odd? Tell us from the Help menu: Contact support or Report a bug.
      </p>
    </>
  );
}

function ContactForm({ user, onToast }: { user: User; onToast: (m: string) => void }) {
  const [topic, setTopic] = useState("General question");
  const [message, setMessage] = useState("");
  const [ready, setReady] = useState(false);

  const subject = `[Support] ${topic}`;
  const body = `${message.trim()}\n\n---\nName: ${user.name}\nEmail: ${user.email}\nMobile: ${user.mobile || "-"}`;

  function submit(e: FormEvent) {
    e.preventDefault();
    if (message.trim()) setReady(true);
  }

  return (
    <form className="hp-form" onSubmit={submit}>
      <div className="hp-form-grid">
        <label className="hp-field">
          <span>Your name</span>
          <input value={user.name} readOnly />
        </label>
        <label className="hp-field">
          <span>Your email</span>
          <input value={user.email} readOnly />
        </label>
      </div>
      <label className="hp-field">
        <span>What do you need help with?</span>
        <select value={topic} onChange={(e) => { setTopic(e.target.value); setReady(false); }}>
          {["General question", "Account & login", "Agents & chats", "Billing & plans", "Privacy & data", "Feedback or suggestion", "Something else"].map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
      </label>
      <label className="hp-field">
        <span>Message</span>
        <textarea rows={7} required placeholder="Describe your question or issue in as much detail as you can…" value={message} onChange={(e) => { setMessage(e.target.value); setReady(false); }} />
      </label>
      {!ready ? (
        <button type="submit" className="btn btn-primary hp-submit" disabled={!message.trim()}>Continue</button>
      ) : (
        <SendPanel subject={subject} body={body} onToast={onToast} />
      )}
    </form>
  );
}

function BugForm({ user, theme, onToast }: { user: User; theme: "dark" | "light"; onToast: (m: string) => void }) {
  const [title, setTitle] = useState("");
  const [steps, setSteps] = useState("");
  const [expected, setExpected] = useState("");
  const [actual, setActual] = useState("");
  const [severity, setSeverity] = useState("Minor - something looks or works oddly");
  const [ready, setReady] = useState(false);

  const subject = `[Bug] ${title.trim()}`;
  const body = [
    `Summary: ${title.trim()}`,
    `Severity: ${severity}`,
    "",
    `Steps to reproduce:\n${steps.trim() || "-"}`,
    "",
    `What I expected:\n${expected.trim() || "-"}`,
    "",
    `What actually happened:\n${actual.trim() || "-"}`,
    "",
    "--- Diagnostics (added automatically) ---",
    `User: ${user.name} <${user.email}>`,
    `Theme: ${theme}`,
    `Browser: ${navigator.userAgent}`,
    `Screen: ${window.screen.width}x${window.screen.height}`,
    `Time: ${new Date().toISOString()}`,
  ].join("\n");

  function touch(setter: (v: string) => void) {
    return (e: { target: { value: string } }) => {
      setter(e.target.value);
      setReady(false);
    };
  }

  return (
    <form
      className="hp-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (title.trim()) setReady(true);
      }}
    >
      <label className="hp-field">
        <span>Short summary</span>
        <input required placeholder="e.g. Send button does nothing in the Capstone agent" value={title} onChange={touch(setTitle)} />
      </label>
      <label className="hp-field">
        <span>How serious is it?</span>
        <select value={severity} onChange={touch(setSeverity)}>
          {["Minor - something looks or works oddly", "Major - I can't finish what I was doing", "Critical - the app is unusable"].map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
      </label>
      <label className="hp-field">
        <span>Steps to reproduce</span>
        <textarea rows={4} placeholder={"1. Open…\n2. Click…\n3. See the problem"} value={steps} onChange={touch(setSteps)} />
      </label>
      <div className="hp-form-grid">
        <label className="hp-field">
          <span>What did you expect?</span>
          <textarea rows={3} value={expected} onChange={touch(setExpected)} />
        </label>
        <label className="hp-field">
          <span>What happened instead?</span>
          <textarea rows={3} value={actual} onChange={touch(setActual)} />
        </label>
      </div>
      <p className="hp-diag">Your browser, screen size, theme and account email are added automatically to help us fix it faster.</p>
      {!ready ? (
        <button type="submit" className="btn btn-primary hp-submit" disabled={!title.trim()}>Continue</button>
      ) : (
        <SendPanel subject={subject} body={body} onToast={onToast} />
      )}
    </form>
  );
}

export default function HelpPage({ page, user, theme, onBack, onNavigate, onToast }: Props) {
  const meta = TITLES[page];
  return (
    <div className="hp-page">
      <div className="hp-inner">
        <button type="button" className="hp-back" onClick={onBack}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M15 6l-6 6 6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Back
        </button>
        <h1 className="hp-title">{meta.title}</h1>
        <p className="hp-sub">{meta.sub}</p>
        {page === "help-center" && <HelpCenter onNavigate={onNavigate} />}
        {page === "release-notes" && <ReleaseNotes />}
        {page === "contact" && <ContactForm user={user} onToast={onToast} />}
        {page === "bug-report" && <BugForm user={user} theme={theme} onToast={onToast} />}
      </div>
    </div>
  );
}
