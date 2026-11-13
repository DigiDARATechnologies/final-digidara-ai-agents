import { useEffect, useState, type CSSProperties } from "react";
import logoOnLight from "../assets/skilldara-logo.png";
import logoOnDark from "../assets/skilldara-logo-dark.png";
import heroImage from "../assets/hero-students.webp";
import careerImage from "../assets/career-path.webp";
import "./LandingPage.css";
import AgentIcon from "./AgentIcon";
import LegalModal from "./LegalModal";
import LandingNav from "./LandingNav";
import { AGENTS } from "../data/landingAgents";

interface LandingPageProps {
  onLogin: () => void;
}

const JOURNEY = [
  { n: "01", title: "Learn & practice", text: "Build your coding, aptitude and communication skills with daily practice.", agents: "Coding · Aptitude · Communication" },
  { n: "02", title: "Build your profile", text: "Create an ATS-ready resume and finish a graded capstone project.", agents: "Resume Builder · Capstone" },
  { n: "03", title: "Prove your skills", text: "Take assessments, earn certificates and climb the leaderboard.", agents: "Certification · Leaderboard" },
  { n: "04", title: "Get hired", text: "Rehearse interviews, then apply to roles that match your profile.", agents: "Mock Interview · Job Agent" },
];

const COLLEGE_FEATURES = [
  { icon: "building", title: "Organization dashboard", text: "See learner activity and progress across your whole institution in one place." },
  { icon: "cap", title: "Class & staff management", text: "Add staff, upload student lists and organize learners by class." },
  { icon: "award", title: "Assessments with proctoring", text: "Run knowledge tests and assessments, and review proctoring reports." },
  { icon: "chat", title: "Reports & leaderboards", text: "Track results, compare cohorts and spot students who need help." },
];

const PLANS = [
  { name: "Free", price: "₹0", coins: "25 coins on signup", text: "Try the agents and see how SkillDARA works.", cta: "Start free" },
  { name: "Basic", price: "₹399", coins: "250 coins", text: "For getting started and light, occasional use.", cta: "Get Basic" },
  { name: "Standard", price: "₹799", coins: "500 coins", text: "For regular learners who use several agents each week.", cta: "Get Standard", popular: true },
  { name: "Premium", price: "₹999", coins: "750 coins", text: "For heavy daily use across every agent.", cta: "Get Premium" },
];

const FAQS = [
  { q: "What is SkillDARA?", a: "SkillDARA is an AI agent workspace for students and job seekers. Each agent focuses on one part of getting career-ready: coding practice, aptitude, communication, resumes, mock interviews, capstone projects, certification and job search." },
  { q: "Who is SkillDARA for?", a: "Students, fresh graduates and job seekers who want to practise and prepare. Colleges and training institutes can also use it to run assessments and track their learners." },
  { q: "Do I need to pay to start?", a: "No. You can create a free account and try the agents. When you want more usage, you can buy coins in one-time packs under Billing inside the app." },
  { q: "How do coins work?", a: "Each agent request uses a few coins. Coins are bought once, never expire, and you can see your balance inside the app. Prices are before GST." },
  { q: "Can my college or institute use SkillDARA?", a: "Yes. Organizations get an admin dashboard, staff and class management, assessments with proctoring and reports. Contact us and we will set it up." },
  { q: "Is my data safe?", a: "Sessions are secured, agent requests are signed, and privacy controls follow data-protection principles including data export and account deletion." },
];

const COMPARE = [
  { need: "Coding practice", us: "Runs your code against real and hidden test cases", other: "Explains code, but does not test it for you" },
  { need: "Mock interviews", us: "Interview rounds with a score and feedback on every answer", other: "You write the prompts and judge the answers yourself" },
  { need: "Your resume", us: "Guided builder with import, ATS analysis and export", other: "Gives you text that you format yourself" },
  { need: "Finding jobs", us: "Ranks roles against your profile with a fit score", other: "No job matching" },
  { need: "Proof of your skills", us: "Assessments, a leaderboard and PDF certificates", other: "Nothing to show an employer" },
  { need: "Tracking progress", us: "One account, saved across devices", other: "Scattered chats to dig through" },
  { need: "For colleges", us: "Organization dashboard, staff tools and proctored tests", other: "Not built for institutions" },
];

const STATS = [
  { n: "8", l: "AI agents in one account" },
  { n: "25", l: "Free coins on signup" },
  { n: "24/7", l: "Practice anytime" },
  { n: "1", l: "Place for your whole prep" },
];

const SUPPORT_EMAIL = "support@digidaraaiagents.com";
const composeUrl = (subject: string) => `https://mail.google.com/mail/?view=cm&fs=1&to=${SUPPORT_EMAIL}&su=${encodeURIComponent(subject)}`;
const COLLEGE_URL = composeUrl("SkillDARA for our college / institute");

function scrollToId(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function SectionHead({ eyebrow, title, hl, text }: { eyebrow: string; title: string; hl: string; text?: string }) {
  return (
    <div className="lp-head">
      <span className="lp-eyebrow">{eyebrow}</span>
      <h2>{title} <em>{hl}</em></h2>
      {text && <p>{text}</p>}
    </div>
  );
}

export default function LandingPage({ onLogin }: LandingPageProps) {
  const [openFaq, setOpenFaq] = useState<number | null>(0);
  const [legalTab, setLegalTab] = useState<"terms" | "privacy" | null>(null);

  function go(id: string) {
    scrollToId(id);
  }

  useEffect(() => {
    const id = sessionStorage.getItem("lp_scroll");
    if (!id) return;
    sessionStorage.removeItem("lp_scroll");
    window.setTimeout(() => scrollToId(id), 60);
  }, []);

  const logo = document.documentElement.dataset.theme === "light" ? logoOnLight : logoOnDark;

  return (
    <div className="lp">
      <LandingNav logo={logo} onNavigate={go} onLogin={onLogin} onSignup={onLogin} />

      <main>
        <section className="lp-hero">
          <div className="lp-wrap lp-hero-inner">
            <div className="lp-hero-copy">
              <span className="lp-pill">AI Agents for Students · Career-ready faster</span>
              <h1>
                Your AI team for <span className="lp-grad">placements &amp; skills</span>
              </h1>
              <p className="lp-lead">
                Practice coding and aptitude, polish your communication, build your resume, rehearse interviews and find jobs. Eight specialized AI agents, one student account.
              </p>
              <div className="lp-cta-row">
                <button type="button" className="lp-btn lp-btn-primary lp-btn-lg" onClick={onLogin}>Start free →</button>
                <button type="button" className="lp-btn lp-btn-outline lp-btn-lg" onClick={() => go("agents")}>Meet the agents</button>
              </div>
              <ul className="lp-trust">
                <li>25 free coins on signup</li>
                <li>No setup needed</li>
                <li>Practice 24/7</li>
              </ul>
            </div>
            <div className="lp-hero-art">
              <img src={heroImage} alt="A student practising with SkillDARA's AI agents on a laptop" width={1536} height={1024} fetchPriority="high" />
            </div>
          </div>
        </section>

        <section className="lp-stats">
          <div className="lp-wrap lp-stats-grid">
            {STATS.map((st) => (
              <div key={st.l} className="lp-stat"><strong>{st.n}</strong><small>{st.l}</small></div>
            ))}
          </div>
        </section>

        <section id="agents" className="lp-section">
          <div className="lp-wrap">
            <SectionHead eyebrow="Our AI agents" title="Eight agents. One goal:" hl="get you hired." text="Each agent is built for one job. Use them together or one at a time, all from a single account." />
            <div className="lp-grid lp-grid-4">
              {AGENTS.map((item) => (
                <article key={item.name} className="lp-card" style={{ "--c": item.color } as CSSProperties}>
                  <div className="lp-card-top">
                    <span className="lp-card-icon"><AgentIcon name={item.icon} size="1.3em" /></span>
                    <span className="lp-card-tag">{item.cat}</span>
                  </div>
                  <h3><a className="lp-card-title-link" href={`/agents/${item.slug}/`}>{item.name}</a></h3>
                  <p>{item.text}</p>
                  <button type="button" className="lp-card-link" onClick={onLogin}>Try this agent →</button>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="journey" className="lp-section lp-section-alt">
          <div className="lp-wrap lp-feature-split">
            <div className="lp-art">
              <img src={careerImage} alt="A student following the SkillDARA path from learning to getting placed, guided by an AI assistant" width={1536} height={1024} loading="lazy" />
            </div>
            <div className="lp-feature-copy">
              <span className="lp-eyebrow">How it works</span>
              <h2>Your path from classroom to <em>career.</em></h2>
              <p className="lp-split-lead">Stop juggling five different apps. SkillDARA gives you one guided route, with an AI agent for every step.</p>
              <ol className="lp-timeline">
                {JOURNEY.map((st) => (
                  <li key={st.n}>
                    <span className="lp-timeline-n">{st.n}</span>
                    <div>
                      <h3>{st.title}</h3>
                      <p>{st.text}</p>
                      <small>{st.agents}</small>
                    </div>
                  </li>
                ))}
              </ol>
              <button type="button" className="lp-btn lp-btn-primary lp-btn-lg" onClick={onLogin}>Start your journey free →</button>
            </div>
          </div>
        </section>

        <section id="compare" className="lp-section">
          <div className="lp-wrap">
            <SectionHead eyebrow="Why SkillDARA" title="A general AI chatbot is great for answers." hl="SkillDARA gets you results." text="Keep using a chatbot for quick questions. Use SkillDARA when you want to practise, get scored and track your progress." />
            <div className="lp-compare" role="table" aria-label="SkillDARA compared with a general AI chatbot">
              <div className="lp-compare-row lp-compare-head" role="row">
                <span role="columnheader">What you need</span>
                <span role="columnheader" className="is-us">SkillDARA</span>
                <span role="columnheader">General AI chatbot</span>
              </div>
              {COMPARE.map((r) => (
                <div key={r.need} className="lp-compare-row" role="row">
                  <b role="rowheader">{r.need}</b>
                  <span role="cell" className="is-us" data-label="SkillDARA"><i aria-hidden="true">✓</i>{r.us}</span>
                  <span role="cell" data-label="General AI chatbot">{r.other}</span>
                </div>
              ))}
            </div>
            <div className="lp-center">
              <button type="button" className="lp-btn lp-btn-primary lp-btn-lg" onClick={onLogin}>Try it free, no setup →</button>
            </div>
          </div>
        </section>

        <section id="colleges" className="lp-section">
          <div className="lp-wrap lp-split">
            <div>
              <span className="lp-eyebrow">For colleges &amp; institutes</span>
              <h2>Make every student <em>placement-ready.</em></h2>
              <p className="lp-split-lead">
                Bring SkillDARA to your campus or training institute. Give every learner the agents, and give your staff the tools to measure progress.
              </p>
              <a className="lp-btn lp-btn-primary lp-btn-lg" href={COLLEGE_URL} target="_blank" rel="noopener noreferrer">Talk to us</a>
            </div>
            <div className="lp-feature-grid">
              {COLLEGE_FEATURES.map((f) => (
                <div key={f.title} className="lp-feature">
                  <span className="lp-card-icon" style={{ "--c": "#4f46e5" } as CSSProperties}><AgentIcon name={f.icon} size="1.3em" /></span>
                  <h3>{f.title}</h3>
                  <p>{f.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="pricing" className="lp-section lp-section-alt">
          <div className="lp-wrap">
            <SectionHead eyebrow="Pricing" title="Simple, one-time" hl="coin packs." text="Each agent request uses a few coins. Coins never expire. Prices are before GST." />
            <div className="lp-grid lp-grid-4 lp-pricing">
              {PLANS.map((p) => (
                <article key={p.name} className={`lp-plan ${p.popular ? "is-popular" : ""}`}>
                  {p.popular && <span className="lp-plan-badge">Most popular</span>}
                  <h3>{p.name}</h3>
                  <div className="lp-plan-price">{p.price}</div>
                  <div className="lp-plan-coins">{p.coins}</div>
                  <p>{p.text}</p>
                  <button type="button" className={`lp-btn ${p.popular ? "lp-btn-primary" : "lp-btn-outline"}`} onClick={onLogin}>{p.cta}</button>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="faq" className="lp-section">
          <div className="lp-wrap lp-faq-wrap">
            <SectionHead eyebrow="FAQ" title="Frequently asked" hl="questions." />
            <div className="lp-faq">
              {FAQS.map((f, i) => (
                <div key={f.q} className={`lp-faq-item ${openFaq === i ? "is-open" : ""}`}>
                  <h3>
                    <button type="button" aria-expanded={openFaq === i} onClick={() => setOpenFaq(openFaq === i ? null : i)}>
                      {f.q}<span aria-hidden="true">{openFaq === i ? "−" : "+"}</span>
                    </button>
                  </h3>
                  {openFaq === i && <div className="lp-faq-a"><p>{f.a}</p></div>}
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="lp-final">
          <div className="lp-wrap">
            <h2>Start preparing smarter today.</h2>
            <p>Create your free account, get 25 coins and open your first agent in minutes.</p>
            <button type="button" className="lp-btn lp-btn-light lp-btn-lg" onClick={onLogin}>Get started free →</button>
          </div>
        </section>
      </main>

      <footer className="lp-footer">
        <div className="lp-wrap lp-footer-grid">
          <div className="lp-footer-brand">
            <img src={logo} alt="SkillDARA" height={40} />
            <p>AI agents that help students practise, build, certify and get hired. One account, eight specialized agents.</p>
            <a href={composeUrl("Support request")} target="_blank" rel="noopener noreferrer">{SUPPORT_EMAIL}</a>
          </div>
          <div>
            <h4>Agents</h4>
            {AGENTS.map((item) => <a key={item.slug} href={`/agents/${item.slug}/`}>{item.name}</a>)}
            <a href="/agents/">All agents</a>
          </div>
          <div>
            <h4>Product</h4>
            <button type="button" onClick={() => scrollToId("journey")}>How it works</button>
            <a href="/pricing/" onClick={(e) => { e.preventDefault(); scrollToId("pricing"); }}>Pricing</a>
            <a href="/for-colleges/" onClick={(e) => { e.preventDefault(); scrollToId("colleges"); }}>For Colleges</a>
            <button type="button" onClick={onLogin}>Log in</button>
            <button type="button" onClick={onLogin}>Sign up free</button>
          </div>
          <div>
            <h4>Resources</h4>
            <a href="/faq/" onClick={(e) => { e.preventDefault(); scrollToId("faq"); }}>FAQ</a>
            <a href={composeUrl("Support request")} target="_blank" rel="noopener noreferrer">Help &amp; support</a>
            <a href={composeUrl("Bug report")} target="_blank" rel="noopener noreferrer">Report a bug</a>
          </div>
          <div>
            <h4>Company</h4>
            <a href={composeUrl("Contact DigiDARA Technologies")} target="_blank" rel="noopener noreferrer">Contact us</a>
            <a href={COLLEGE_URL} target="_blank" rel="noopener noreferrer">Institution enquiries</a>
            <button type="button" onClick={() => setLegalTab("terms")}>Terms of Service</button>
            <button type="button" onClick={() => setLegalTab("privacy")}>Privacy Policy</button>
          </div>
        </div>
        <div className="lp-wrap lp-footer-bottom">
          <span>© {new Date().getFullYear()} DigiDARA Technologies. All rights reserved.</span>
          <span className="lp-footer-badges"><b>Secure sessions</b><b>Privacy-first</b><b>Data export &amp; deletion</b></span>
        </div>
      </footer>
      <LegalModal open={legalTab !== null} initialTab={legalTab ?? "terms"} onClose={() => setLegalTab(null)} />
    </div>
  );
}
