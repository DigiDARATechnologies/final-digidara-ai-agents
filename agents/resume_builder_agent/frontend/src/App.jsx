import { useState } from "react";
import logo from "./assets/logo.png";
import { Link, NavLink } from "./router.jsx";

export default function App({ children }) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  function closeMenu() {
    setIsMenuOpen(false);
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" onClick={closeMenu} to="/">
          <img className="brand-logo" src={logo} alt="DD Logo" />
          <span className="brand-text">Digidara AI Resume</span>
        </Link>

        <button
          aria-controls="primary-navigation"
          aria-expanded={isMenuOpen}
          className="mobile-nav-toggle"
          onClick={() => setIsMenuOpen((current) => !current)}
          type="button"
        >
          <span />
          <span />
          <span />
          Menu
        </button>

        <nav
          aria-label="Primary navigation"
          className={isMenuOpen ? "topnav open" : "topnav"}
          id="primary-navigation"
        >
          <a href="/#templates" onClick={closeMenu}>Templates</a>
          <a href="/#ats-review" onClick={closeMenu}>ATS Review</a>
          <NavLink onClick={closeMenu} to="/resumes">Dashboard</NavLink>
          <NavLink className="topnav-primary" onClick={closeMenu} to="/resumes">
            Open Dossier
          </NavLink>
        </nav>
      </header>

      <main>{children}</main>

      <footer className="app-footer">
        <div className="footer-content">
          <p>&copy; {new Date().getFullYear()} Digidara AI Resume - secure resume dossiers, ATS review, and text-based PDF export.</p>
        </div>
      </footer>
    </div>
  );
}

