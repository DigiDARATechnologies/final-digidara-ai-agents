import { createContext, useContext, useEffect, useMemo, useState } from "react";

const RouterContext = createContext(null);

export function RouterProvider({ children }) {
  const [location, setLocation] = useState(() => readLocation());

  useEffect(() => {
    const sync = () => setLocation(readLocation());
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);

  const value = useMemo(() => ({
    location,
    navigate(to, options = {}) {
      const method = options.replace ? "replaceState" : "pushState";
      window.history[method]({ usr: options.state ?? null }, "", to);
      setLocation(readLocation());
      window.scrollTo({ top: 0, behavior: "auto" });
    },
  }), [location]);

  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
}

export function Link({ children, onClick, to, ...props }) {
  const navigate = useNavigate();
  return (
    <a
      {...props}
      href={to}
      onClick={(event) => {
        onClick?.(event);
        if (
          event.defaultPrevented
          || event.button !== 0
          || event.metaKey
          || event.ctrlKey
          || event.shiftKey
          || event.altKey
        ) return;
        event.preventDefault();
        navigate(to);
      }}
    >
      {children}
    </a>
  );
}

export function NavLink({ children, className = "", end = false, to, ...props }) {
  const { pathname } = useLocation();
  const active = end ? pathname === to : pathname === to || pathname.startsWith(`${to}/`);
  const resolvedClassName = typeof className === "function"
    ? className({ isActive: active })
    : [className, active ? "active" : ""].filter(Boolean).join(" ");
  return <Link {...props} className={resolvedClassName} to={to}>{children}</Link>;
}

export function useNavigate() {
  const context = useContext(RouterContext);
  if (!context) throw new Error("useNavigate must be used inside RouterProvider");
  return context.navigate;
}

export function useLocation() {
  const context = useContext(RouterContext);
  if (!context) throw new Error("useLocation must be used inside RouterProvider");
  return context.location;
}

export function useParams() {
  const { pathname } = useLocation();
  const resumeMatch = pathname.match(/^\/resume\/([^/]+)\/?$/);
  return resumeMatch ? { resumeId: decodeURIComponent(resumeMatch[1]) } : {};
}

function readLocation() {
  return {
    pathname: window.location.pathname,
    search: window.location.search,
    hash: window.location.hash,
    state: window.history.state?.usr ?? null,
  };
}
