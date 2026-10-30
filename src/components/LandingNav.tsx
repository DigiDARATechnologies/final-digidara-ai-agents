import "./LandingPage.css";
import { useState } from "react";

const NAV_ITEMS = [
  { id: "agents", label: "Agents" },
  { id: "journey", label: "How it works" },
  { id: "colleges", label: "For Colleges" },
  { id: "pricing", label: "Pricing" },
  { id: "faq", label: "FAQ" },
];

interface LandingNavProps {
  logo: string;
  onNavigate: (id: string) => void;
  onLogin: () => void;
  onSignup: () => void;
  onHome?: () => void;
}

/** Top bar shared by the landing page and the login page. Styled by LandingPage.css (.lp-nav*). */
export default function LandingNav({ logo, onNavigate, onLogin, onSignup, onHome }: LandingNavProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  function go(id: string) {
    setMenuOpen(false);
    onNavigate(id);
  }

  return (
    <header className="lp-nav">
      <div className="lp-wrap lp-nav-inner">
        <a className="lp-brand" href="/" aria-label="SkillDARA home" onClick={onHome ? (e) => { e.preventDefault(); onHome(); } : undefined}>
          <img src={logo} alt="SkillDARA" height={44} />
        </a>
        <nav className={`lp-links ${menuOpen ? "is-open" : ""}`} aria-label="Primary">
          {NAV_ITEMS.map((item) => (
            <button key={item.id} type="button" onClick={() => go(item.id)}>{item.label}</button>
          ))}
          <button type="button" className="lp-links-login" onClick={() => { setMenuOpen(false); onLogin(); }}>Login</button>
        </nav>
        <div className="lp-nav-actions">
          <button type="button" className="lp-btn lp-btn-ghost lp-hide-sm" onClick={onLogin}>Login</button>
          <button type="button" className="lp-btn lp-btn-primary" onClick={onSignup}>Get started free</button>
          <button type="button" className="lp-icon-btn lp-burger" aria-label="Toggle menu" aria-expanded={menuOpen} onClick={() => setMenuOpen((v) => !v)}>
            {menuOpen ? "✕" : "☰"}
          </button>
        </div>
      </div>
    </header>
  );
}
