import { useEffect, useRef, useState, type CSSProperties, type KeyboardEvent, type MouseEvent, type ReactNode } from "react";
import logoOnDark from "../assets/logo-navbar-dark.png";
import logoOnLight from "../assets/logo-navbar-light.png";
import "./LandingPage.css";

interface LandingPageProps {
  theme: "dark" | "light";
  onToggleTheme: () => void;
  onLogin: () => void;
}

const INDUSTRIES = [
  { color: "#6f8dff", tag: "Learn & grow", icon: "🎓", name: "Education & Training", text: "Coding practice, aptitude drills, capstone projects and certifications for learners and institutions." },
  { color: "#38d0f5", tag: "Guest experience", icon: "✈️", name: "Travel & Hospitality", text: "Itinerary planning, booking support and multilingual guest assistance that never sleeps." },
  { color: "#f2a71b", tag: "Build smarter", icon: "🏗️", name: "Construction & Real Estate", text: "Project tracking, site reporting, estimating and compliance paperwork handled by agents." },
  { color: "#34d399", tag: "Care, simplified", icon: "🏥", name: "Healthcare", text: "Appointment flows, patient FAQs and documentation support, built with privacy first." },
  { color: "#c084fc", tag: "Serve faster", icon: "🏦", name: "Finance & Retail", text: "Customer support, report summaries and catalog or inventory assistants for growing teams." },
  { color: "#fb7185", tag: "Built for you", icon: "🚀", name: "Your Industry", text: "Tell us your workflow. We design, build and deploy a specialized agent around it." },
];

const AGENTS = [
  { color: "#16a34a", icon: "🎓", name: "Capstone Project Agent", text: "Guides a project from idea to graded submission with eligibility checks and review." },
  { color: "#eab308", icon: "⌨️", name: "Coding Practice Agent", text: "Real coding problems, sandboxed test runs and an AI tutor when you get stuck." },
  { color: "#f43f5e", icon: "🗣️", name: "Communication Coach", text: "Pronunciation, speaking and writing practice scored by AI, with daily challenges." },
  { color: "#f97316", icon: "🧮", name: "Aptitude Trainer", text: "Quantitative, logical and verbal practice sets with timed tests and explanations." },
  { color: "#8b5cf6", icon: "🎤", name: "Mock Interview Agent", text: "Technical and HR interview rounds with per-answer scoring and feedback." },
  { color: "#14b8a6", icon: "📄", name: "Resume Builder", text: "Create, import, analyze and export ATS-friendly resumes in a guided workflow." },
  { color: "#3b82f6", icon: "🔎", name: "Job Fetching Agent", text: "Finds roles that match your profile and ranks them with an explainable fit score." },
  { color: "#a78bfa", icon: "📜", name: "AI Certification Agent", text: "Exam generation, chat-based assessment, leaderboard and PDF certificates." },
];

const STEPS = [
  { n: "1", title: "Create a free account", text: "Sign up with email or Google in under a minute." },
  { n: "2", title: "Pick or ask for an agent", text: "Open a ready-made agent, or just describe what you need and be routed to the right one." },
  { n: "3", title: "Get work done", text: "Chat, practice, generate and export. Your progress is saved across devices." },
];

const FAQS = [
  { q: "What is DigiDARA AI Agents?", a: "DigiDARA AI Agents is an AI agent workspace where businesses, teams and individuals use specialized AI agents for learning, careers, communication, hiring and industry workflows, all under one account." },
  { q: "Who is DigiDARA AI Agents for?", a: "Anyone, anywhere in the world. Students and job seekers use it for practice and careers, while companies in travel, construction, education and other industries use it to automate repetitive work with custom AI agents." },
  { q: "Can DigiDARA build a custom AI agent for my industry?", a: "Yes. DigiDARA designs and builds specialized AI agents for industries such as travel, construction, healthcare, finance and education, shaped around your own workflow." },
  { q: "Is my data safe?", a: "Sessions are secured, agent requests are signed, and privacy controls follow data-protection principles including data export and account deletion." },
  { q: "How much does it cost?", a: "You can start free. Paid plans add more usage and are shown inside the app under Billing." },
];

function Reveal({ children, delay = 0, className = "" }: { children: ReactNode; delay?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") { setShown(true); return; }
    const io = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) { setShown(true); io.disconnect(); }
    }, { threshold: 0.12 });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div ref={ref} className={`lp-reveal ${shown ? "is-in" : ""} ${className}`} style={{ transitionDelay: `${delay}ms` }}>
      {children}
    </div>
  );
}

const REDUCED_MOTION = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const TYPE_WORDS = ["every industry", "travel teams", "construction", "education", "healthcare", "your business"];

function Typewriter({ words }: { words: string[] }) {
  const [text, setText] = useState(words[0]);
  useEffect(() => {
    if (REDUCED_MOTION()) return;
    let w = 0;
    let c = words[0].length;
    let deleting = true;
    let timer = 0;
    const tick = () => {
      const word = words[w];
      c += deleting ? -1 : 1;
      setText(word.slice(0, c));
      let delay = deleting ? 45 : 85;
      if (!deleting && c === word.length) { deleting = true; delay = 1700; }
      else if (deleting && c === 0) { deleting = false; w = (w + 1) % words.length; delay = 250; }
      timer = window.setTimeout(tick, delay);
    };
    timer = window.setTimeout(tick, 1800);
    return () => window.clearTimeout(timer);
  }, [words]);
  return <>{text}<span className="lp-caret" /></>;
}

function CountUp({ to, suffix = "" }: { to: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined" || REDUCED_MOTION()) { setN(to); return; }
    let raf = 0;
    const io = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      io.disconnect();
      const t0 = performance.now();
      const step = (t: number) => {
        const p = Math.min((t - t0) / 1400, 1);
        setN(Math.round(to * (1 - Math.pow(1 - p, 3))));
        if (p < 1) raf = requestAnimationFrame(step);
      };
      raf = requestAnimationFrame(step);
    }, { threshold: 0.4 });
    io.observe(el);
    return () => { io.disconnect(); cancelAnimationFrame(raf); };
  }, [to]);
  return <span ref={ref}>{n}{suffix}</span>;
}

/** Drifting dots that link up with each other and with the cursor. */
function ParticleBg({ theme }: { theme: "dark" | "light" }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    const parent = canvas?.parentElement;
    if (!canvas || !ctx || !parent || REDUCED_MOTION()) return;
    const rgb = theme === "dark" ? "140,175,255" : "40,81,216";
    const mouse = { x: -9999, y: -9999 };
    let w = 0;
    let h = 0;
    let raf = 0;
    let visible = true;
    let dots: { x: number; y: number; vx: number; vy: number; r: number }[] = [];
    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = parent.clientWidth;
      h = parent.clientHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.min(70, Math.round((w * h) / 18000));
      dots = Array.from({ length: count }, () => ({
        x: Math.random() * w, y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.4, vy: (Math.random() - 0.5) * 0.4, r: 1 + Math.random() * 1.8,
      }));
    };
    const draw = () => {
      raf = requestAnimationFrame(draw);
      if (!visible) return;
      ctx.clearRect(0, 0, w, h);
      for (let i = 0; i < dots.length; i++) {
        const d = dots[i];
        d.x += d.vx; d.y += d.vy;
        if (d.x < 0 || d.x > w) d.vx *= -1;
        if (d.y < 0 || d.y > h) d.vy *= -1;
        ctx.beginPath();
        ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${rgb},.75)`;
        ctx.fill();
        for (let j = i + 1; j < dots.length; j++) {
          const o = dots[j];
          const dist = Math.hypot(d.x - o.x, d.y - o.y);
          if (dist < 120) {
            ctx.strokeStyle = `rgba(${rgb},${0.22 * (1 - dist / 120)})`;
            ctx.beginPath(); ctx.moveTo(d.x, d.y); ctx.lineTo(o.x, o.y); ctx.stroke();
          }
        }
        const md = Math.hypot(d.x - mouse.x, d.y - mouse.y);
        if (md < 170) {
          ctx.strokeStyle = `rgba(242,167,27,${0.55 * (1 - md / 170)})`;
          ctx.beginPath(); ctx.moveTo(d.x, d.y); ctx.lineTo(mouse.x, mouse.y); ctx.stroke();
        }
      }
    };
    const onMove = (e: globalThis.MouseEvent) => {
      const r = parent.getBoundingClientRect();
      mouse.x = e.clientX - r.left; mouse.y = e.clientY - r.top;
    };
    const onLeave = () => { mouse.x = -9999; mouse.y = -9999; };
    const io = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; });
    resize();
    io.observe(parent);
    window.addEventListener("resize", resize);
    parent.addEventListener("mousemove", onMove);
    parent.addEventListener("mouseleave", onLeave);
    raf = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(raf); io.disconnect();
      window.removeEventListener("resize", resize);
      parent.removeEventListener("mousemove", onMove);
      parent.removeEventListener("mouseleave", onLeave);
    };
  }, [theme]);
  return <canvas ref={ref} className="lp-particles" aria-hidden="true" />;
}

function spotlight(e: MouseEvent<HTMLElement>) {
  const el = e.currentTarget;
  const r = el.getBoundingClientRect();
  const x = e.clientX - r.left;
  const y = e.clientY - r.top;
  el.style.setProperty("--mx", `${x}px`);
  el.style.setProperty("--my", `${y}px`);
  el.style.setProperty("--ry", `${(x / r.width - 0.5) * 10}deg`);
  el.style.setProperty("--rx", `${-(y / r.height - 0.5) * 10}deg`);
}

function unspot(e: MouseEvent<HTMLElement>) {
  e.currentTarget.style.setProperty("--rx", "0deg");
  e.currentTarget.style.setProperty("--ry", "0deg");
}

function SectionHead({ eyebrow, title, hl, text }: { eyebrow: string; title: string; hl: string; text?: string }) {
  return (
    <Reveal className="lp-head">
      <span className="lp-eyebrow"><i />{eyebrow}<i /></span>
      <h2>{title} <em>{hl}</em></h2>
      {text && <p>{text}</p>}
    </Reveal>
  );
}

const SUPPORT_EMAIL = "support@digidaraaiagents.com";
const COMPOSE_URL = `https://mail.google.com/mail/?view=cm&fs=1&to=${SUPPORT_EMAIL}&su=${encodeURIComponent("Custom AI agent enquiry")}`;

function cardClick(onActivate: () => void) {
  return {
    role: "button" as const,
    tabIndex: 0,
    onClick: onActivate,
    onKeyDown: (e: KeyboardEvent<HTMLElement>) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onActivate(); }
    },
  };
}

function scrollToId(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export default function LandingPage({ theme, onToggleTheme, onLogin }: LandingPageProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [openFaq, setOpenFaq] = useState<number | null>(0);

  const rootRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    const onScroll = () => {
      setScrolled(el.scrollTop > 12);
      const max = el.scrollHeight - el.clientHeight;
      el.style.setProperty("--p", max > 0 ? String(el.scrollTop / max) : "0");
    };
    onScroll();
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  const stageRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onMove = (e: globalThis.MouseEvent) => {
      const st = stageRef.current;
      if (!st) return;
      const r = st.getBoundingClientRect();
      const dx = (e.clientX - (r.left + r.width / 2)) / window.innerWidth;
      const dy = (e.clientY - (r.top + r.height / 2)) / window.innerHeight;
      st.style.setProperty("--ex", `${Math.max(-1, Math.min(1, dx * 3)) * 7}px`);
      st.style.setProperty("--ey", `${Math.max(-1, Math.min(1, dy * 3)) * 5}px`);
    };
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, []);

  function go(id: string) {
    setMenuOpen(false);
    scrollToId(id);
  }

  const logo = theme === "dark" ? logoOnDark : logoOnLight;

  return (
    <div className="lp" ref={rootRef}>
      <header className={`lp-nav ${scrolled ? "is-scrolled" : ""}`}>
        <div className="lp-progress" aria-hidden="true" />
        <div className="lp-wrap lp-nav-inner">
          <a className="lp-brand" href="/" aria-label="DigiDARA AI Agents home">
            <img src={logo} alt="DigiDARA AI Agents" height={68} />
          </a>
          <nav className={`lp-links ${menuOpen ? "is-open" : ""}`} aria-label="Primary">
            <button type="button" onClick={() => go("industries")}>Industries</button>
            <button type="button" onClick={() => go("agents")}>Agents</button>
            <button type="button" onClick={() => go("how-it-works")}>How it works</button>
            <button type="button" onClick={() => go("faq")}>FAQ</button>
          </nav>
          <div className="lp-nav-actions">
            <button type="button" className="lp-icon-btn" onClick={onToggleTheme} aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}>
              {theme === "dark" ? "☀️" : "🌙"}
            </button>
            <button type="button" className="lp-btn lp-btn-ghost" onClick={onLogin}>Login</button>
            <button type="button" className="lp-btn lp-btn-primary lp-hide-sm" onClick={onLogin}>Get started free</button>
            <button type="button" className="lp-icon-btn lp-burger" aria-label="Toggle menu" aria-expanded={menuOpen} onClick={() => setMenuOpen((v) => !v)}>
              {menuOpen ? "✕" : "☰"}
            </button>
          </div>
        </div>
      </header>

      <main>
        <section className="lp-hero">
          <div className="lp-orb lp-orb-a" aria-hidden="true" />
          <div className="lp-orb lp-orb-b" aria-hidden="true" />
          <div className="lp-orb lp-orb-c" aria-hidden="true" />
          <ParticleBg theme={theme} />
          <div className="lp-wrap lp-hero-inner">
            <div className="lp-hero-copy">
              <span className="lp-pill"><i /> AI agents for every industry, worldwide</span>
              <h1>
                AI agents that do the work,<br />
                <span className="lp-grad">for <Typewriter words={TYPE_WORDS} />.</span>
              </h1>
              <p className="lp-lead">
                DigiDARA AI Agents gives people and businesses specialized AI agents for learning, careers,
                communication, travel, construction and more. Open a ready-made agent today, or have us build
                one around your workflow.
              </p>
              <div className="lp-cta-row">
                <button type="button" className="lp-btn lp-btn-primary lp-btn-lg" onClick={onLogin}>Get started free →</button>
                <button type="button" className="lp-btn lp-btn-outline lp-btn-lg" onClick={() => go("agents")}>Explore agents</button>
              </div>
              <ul className="lp-trust">
                <li>🌍 Built for users worldwide</li>
                <li>🔒 Secure by design</li>
                <li>⚡ Available 24/7</li>
              </ul>
            </div>

            <div className="lp-hero-visual" aria-hidden="true">
              <div className="lp-bot-stage" ref={stageRef}>
                <div className="lp-bot-ring lp-bot-ring-a" />
                <div className="lp-bot-ring lp-bot-ring-b" />
                <div className="lp-bot-bubble">
                  <strong>Hi there! 👋</strong>
                  <span>Welcome to DigiDARA AI Agents</span>
                </div>
                <svg className="lp-bot" viewBox="0 0 400 440" role="img" aria-label="Friendly DigiDARA AI robot waving hello">
                  <defs>
                    <linearGradient id="bot-body" x1="0" y1="0" x2="1" y2="1">
                      <stop offset="0" stopColor="#7fa0ff" /><stop offset="1" stopColor="#2851d8" />
                    </linearGradient>
                    <linearGradient id="bot-head" x1="0" y1="0" x2="1" y2="1">
                      <stop offset="0" stopColor="#ffffff" /><stop offset="1" stopColor="#c9d6ff" />
                    </linearGradient>
                    <radialGradient id="bot-eye" cx=".5" cy=".4" r=".7">
                      <stop offset="0" stopColor="#c8fbff" /><stop offset="1" stopColor="#25c8f0" />
                    </radialGradient>
                    <filter id="bot-glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="5" /></filter>
                  </defs>
                  <ellipse className="lp-bot-shadow" cx="200" cy="415" rx="95" ry="12" fill="#000" opacity=".28" />
                  <g className="lp-bot-float">
                    <line x1="200" y1="92" x2="200" y2="122" stroke="#9db4ff" strokeWidth="6" strokeLinecap="round" />
                    <circle className="lp-bot-antenna" cx="200" cy="82" r="11" fill="#f2a71b" />
                    <circle cx="200" cy="82" r="18" fill="#f2a71b" opacity=".4" filter="url(#bot-glow)" />
                    <g className="lp-bot-arm lp-bot-arm-left">
                      <rect x="108" y="268" width="24" height="86" rx="12" fill="url(#bot-body)" />
                      <circle cx="120" cy="360" r="16" fill="url(#bot-head)" />
                    </g>
                    <rect x="132" y="262" width="136" height="124" rx="38" fill="url(#bot-body)" />
                    <rect x="158" y="288" width="84" height="56" rx="20" fill="#0b1740" opacity=".55" />
                    <text x="200" y="326" textAnchor="middle" fontSize="34" fontWeight="900" fill="#fff" fontFamily="Inter, sans-serif">D</text>
                    <circle className="lp-bot-led" cx="200" cy="362" r="6" fill="#4ade80" />
                    <g className="lp-bot-arm lp-bot-arm-right">
                      <rect x="268" y="268" width="24" height="86" rx="12" fill="url(#bot-body)" />
                      <circle cx="280" cy="360" r="17" fill="url(#bot-head)" />
                    </g>
                    <circle cx="106" cy="188" r="16" fill="#9db4ff" /><circle cx="294" cy="188" r="16" fill="#9db4ff" />
                    <rect x="112" y="122" width="176" height="140" rx="52" fill="url(#bot-head)" />
                    <rect x="132" y="144" width="136" height="92" rx="34" fill="#0b1740" />
                    <g className="lp-bot-look"><g className="lp-bot-eyes">
                      <ellipse cx="170" cy="184" rx="14" ry="17" fill="url(#bot-eye)" />
                      <ellipse cx="230" cy="184" rx="14" ry="17" fill="url(#bot-eye)" />
                    </g></g>
                    <path className="lp-bot-smile" d="M176 210 Q200 230 224 210" stroke="#25c8f0" strokeWidth="6" fill="none" strokeLinecap="round" />
                    <circle cx="150" cy="208" r="7" fill="#fb7185" opacity=".5" /><circle cx="250" cy="208" r="7" fill="#fb7185" opacity=".5" />
                  </g>
                </svg>
                <span className="lp-spark lp-spark-a">✦</span>
                <span className="lp-spark lp-spark-b">✦</span>
                <span className="lp-spark lp-spark-c">✦</span>
              </div>
              <span className="lp-float lp-float-a">✈️ Travel</span>
              <span className="lp-float lp-float-b">🏗️ Construction</span>
              <span className="lp-float lp-float-c">🎓 Education</span>
            </div>
          </div>
        </section>

        <div className="lp-marquee" aria-hidden="true">
          <div className="lp-marquee-track">
            {[0, 1].map((k) => INDUSTRIES.concat(INDUSTRIES).map((it, i) => (
              <span key={`${k}-${i}`} style={{ "--c": it.color } as CSSProperties}>{it.icon} {it.name}</span>
            )))}
          </div>
        </div>

        <div className="lp-marquee lp-marquee-rev" aria-hidden="true">
          <div className="lp-marquee-track">
            {[0, 1].map((k) => AGENTS.concat(AGENTS).map((it, i) => (
              <span key={`${k}-${i}`} style={{ "--c": it.color } as CSSProperties}>{it.icon} {it.name}</span>
            )))}
          </div>
        </div>

        <section className="lp-stats">
          <div className="lp-wrap lp-stats-grid">
            {[
              { i: "🤖", n: "8+", count: 8, l: "Live specialized agents" },
              { i: "🏭", n: "Any industry", l: "Custom agents on request" },
              { i: "⏱️", n: "24/7", l: "Always available" },
              { i: "🌍", n: "Global", l: "Used by learners and teams" },
            ].map((st, k) => (
              <Reveal key={st.l} delay={k * 80}>
                <div className="lp-stat"><span>{st.i}</span><strong>{st.count ? <CountUp to={st.count} suffix="+" /> : st.n}</strong><small>{st.l}</small></div>
              </Reveal>
            ))}
          </div>
        </section>

        <section id="industries" className="lp-section lp-bg-grid">
          <div className="lp-wrap">
            <SectionHead eyebrow="Industries" title="One platform. Agents for" hl="every kind of work." text="We are not only for students. DigiDARA builds AI agents for the industries where repetitive work slows people down." />
            <div className="lp-grid lp-bento">
              {INDUSTRIES.map((item, i) => (
                <Reveal key={item.name} delay={i * 70} className={`zoom ${i === 0 || i === 5 ? "lp-span-2" : ""}`}>
                  <article className="lp-card lp-card-ind" style={{ "--c": item.color } as CSSProperties} onMouseMove={spotlight} onMouseLeave={unspot} {...cardClick(onLogin)}>
                    <span className="lp-card-no">{String(i + 1).padStart(2, "0")}</span>
                    <span className="lp-card-icon">{item.icon}</span>
                    <span className="lp-card-tag">{item.tag}</span>
                    <h3>{item.name}</h3>
                    <p>{item.text}</p>
                  </article>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <section id="agents" className="lp-section lp-section-alt lp-bg-glow">
          <div className="lp-wrap">
            <SectionHead eyebrow="Our agents" title="Ready-to-use AI agents," hl="live today." text="Each agent is purpose-built and works inside one account. More industry agents are on the way." />
            <div className="lp-grid lp-grid-4">
              {AGENTS.map((item, i) => (
                <Reveal key={item.name} delay={(i % 4) * 70}>
                  <article className="lp-card lp-card-agent" style={{ "--c": item.color } as CSSProperties} onMouseMove={spotlight} onMouseLeave={unspot} {...cardClick(onLogin)}>
                    <span className="lp-live"><i />Live</span>
                    <span className="lp-card-icon">{item.icon}</span>
                    <h3>{item.name}</h3>
                    <p>{item.text}</p>
                    <span className="lp-card-link">Open agent <b>→</b></span>
                  </article>
                </Reveal>
              ))}
            </div>
            <Reveal className="lp-center">
              <button type="button" className="lp-btn lp-btn-primary lp-btn-lg" onClick={onLogin}>Try the agents free →</button>
            </Reveal>
          </div>
        </section>

        <section id="how-it-works" className="lp-section lp-bg-grid">
          <div className="lp-wrap">
            <SectionHead eyebrow="How it works" title="From sign-up to results in" hl="three steps." />
            <div className="lp-grid lp-grid-3 lp-steps">
              {STEPS.map((st, i) => (
                <Reveal key={st.n} delay={i * 100}>
                  <div className="lp-step">
                    <span className="lp-step-n">{st.n}</span>
                    <h3>{st.title}</h3>
                    <p>{st.text}</p>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <section className="lp-section lp-section-alt">
          <div className="lp-wrap lp-split">
            <Reveal className="from-left">
              <span className="lp-eyebrow"><i />Why DigiDARA<i /></span>
              <h2>Built to be useful, trusted and <em>easy to adopt.</em></h2>
              <ul className="lp-checks">
                <li>One account for every agent, with chat history across devices</li>
                <li>Specialized agents, not a single generic chatbot</li>
                <li>Privacy-first: data export and account deletion built in</li>
                <li>Custom agents designed around your own industry workflow</li>
              </ul>
            </Reveal>
            <Reveal delay={120} className="from-right">
              <div className="lp-cta-card">
                <h3>Need an agent for your business?</h3>
                <p>Tell us about your workflow in travel, construction, education or any other field, and we will build it with you.</p>
                <a className="lp-btn lp-btn-primary" href={COMPOSE_URL} target="_blank" rel="noopener noreferrer">Talk to us</a>
              </div>
            </Reveal>
          </div>
        </section>

        <section id="faq" className="lp-section">
          <div className="lp-wrap lp-faq-wrap">
            <Reveal className="lp-head">
              <span className="lp-eyebrow"><i />FAQ<i /></span>
              <h2>Frequently asked <em>questions</em></h2>
            </Reveal>
            <div className="lp-faq">
              {FAQS.map((f, i) => (
                <div key={f.q} className={`lp-faq-item ${openFaq === i ? "is-open" : ""}`}>
                  <h3>
                    <button type="button" aria-expanded={openFaq === i} onClick={() => setOpenFaq(openFaq === i ? null : i)}>
                      {f.q}<span aria-hidden="true">{openFaq === i ? "−" : "+"}</span>
                    </button>
                  </h3>
                  <div className="lp-faq-a"><p>{f.a}</p></div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="lp-final">
          <div className="lp-orb lp-orb-a" aria-hidden="true" /><div className="lp-orb lp-orb-b" aria-hidden="true" />
          <div className="lp-wrap">
            <Reveal>
              <h2>Put AI agents to work <em>today.</em></h2>
              <p>Create your free account and open your first agent in minutes.</p>
              <button type="button" className="lp-btn lp-btn-light lp-btn-lg" onClick={onLogin}>Get started free →</button>
            </Reveal>
          </div>
        </section>
      </main>

      <footer className="lp-footer">
        <div className="lp-wrap lp-footer-grid">
          <div>
            <img src={logo} alt="DigiDARA AI Agents" height={68} />
            <p>AI agents for every industry, built for users around the world.</p>
          </div>
          <div>
            <h4>Product</h4>
            <button type="button" onClick={() => scrollToId("agents")}>Agents</button>
            <button type="button" onClick={() => scrollToId("industries")}>Industries</button>
            <button type="button" onClick={() => scrollToId("how-it-works")}>How it works</button>
            <button type="button" onClick={onLogin}>Login / Sign up</button>
          </div>
          <div>
            <h4>Company</h4>
            <button type="button" onClick={() => scrollToId("faq")}>FAQ</button>
          </div>
          <div>
            <h4>Get in touch</h4>
            <a href={COMPOSE_URL} target="_blank" rel="noopener noreferrer">support@digidaraaiagents.com</a>
          </div>
        </div>
        <div className="lp-wrap lp-footer-bottom">
          <span>© {new Date().getFullYear()} DigiDARA Technologies. All rights reserved.</span>
          <span>DigiDARA AI Agents</span>
        </div>
      </footer>
    </div>
  );
}
