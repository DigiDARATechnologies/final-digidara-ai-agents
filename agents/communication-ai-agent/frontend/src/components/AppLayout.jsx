import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import {
  BarChart3, BookOpenCheck, ChevronRight, History, Menu, Mic2,
  PenLine, Sparkles, Target, UserRound, X,
} from "lucide-react";
import { useAuth } from "../context/AuthContext.jsx";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", caption: "Your learning overview", icon: BarChart3, end: true },
  { to: "/speaking", label: "Speaking", caption: "Build confidence", icon: Mic2 },
  { to: "/writing", label: "Writing", caption: "Write with clarity", icon: PenLine },
  { to: "/pronunciation", label: "Pronunciation", caption: "Sound more natural", icon: Target },
  { to: "/history", label: "History", caption: "Review your progress", icon: History },
  { to: "/profile", label: "Profile", caption: "Learning preferences", icon: UserRound },
];

export default function AppLayout() {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const current = NAV_ITEMS.find((item) => item.end ? location.pathname === "/" : location.pathname.startsWith(item.to)) || NAV_ITEMS[0];
  const initial = user?.name?.[0]?.toUpperCase() || "?";

  const handleGuardedNavigate = async (event, to) => {
    const isSameRoute = location.pathname === to || (!NAV_ITEMS.find((item) => item.to === to)?.end && to !== "/" && location.pathname.startsWith(to));
    const requestLeave = window.__communiCoachRequestLeave;
    if (typeof requestLeave !== "function" || isSameRoute) {
      setSidebarOpen(false);
      return;
    }

    event.preventDefault();
    const canLeave = await requestLeave();
    if (canLeave) {
      setSidebarOpen(false);
      navigate(to);
    }
  };

  return (
    <div className="app-shell flex h-screen w-full overflow-hidden text-slate-800">
      {sidebarOpen && (
        <button
          className="fixed inset-0 z-30 bg-slate-900/30 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-label="Close navigation"
        />
      )}

      <aside className={`app-sidebar fixed inset-y-0 left-0 z-40 flex w-[282px] shrink-0 flex-col border-r px-4 py-5 transition-transform duration-300 lg:static lg:translate-x-0 ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="mb-7 flex items-center gap-3 px-2">
            <div className="brand-mark"><Sparkles size={20} strokeWidth={2.4} /></div>
            <div className="min-w-0">
              <p className="truncate text-[15px] font-bold tracking-tight text-slate-900">Communication Coach</p>
              <p className="mt-0.5 text-[11px] font-medium tracking-wide text-brand-600">AI LEARNING STUDIO</p>
            </div>
          </div>

          <div className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">Workspace</div>
          <nav className="space-y-1.5 overflow-y-auto">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  onClick={(event) => handleGuardedNavigate(event, item.to)}
                  className={({ isActive }) => `nav-item group flex items-center gap-3 rounded-2xl px-3 py-2.5 transition-all ${isActive ? "nav-item-active" : ""}`}
                >
                  <span className="nav-icon flex h-9 w-9 shrink-0 items-center justify-center rounded-xl"><Icon size={18} /></span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-semibold">{item.label}</span>
                    <span className="block truncate text-[11px] opacity-70">{item.caption}</span>
                  </span>
                  <ChevronRight className="nav-chevron opacity-0 transition group-hover:opacity-70" size={15} />
                </NavLink>
              );
            })}
          </nav>
        </div>

        <div className="sidebar-tip mb-3 rounded-2xl p-4">
          <div className="mb-2 flex items-center gap-2 text-xs font-bold text-slate-800"><BookOpenCheck size={15} /> Today's tip</div>
          <p className="text-[11px] leading-relaxed text-slate-600">Small, consistent practice sessions create lasting communication skills.</p>
        </div>
        <div className="profile-chip flex items-center gap-3 rounded-2xl p-3">
          <NavLink to="/profile" onClick={(event) => handleGuardedNavigate(event, "/profile")} className="flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-violet-500 text-sm font-bold text-white shadow-lg shadow-brand-500/20 transition hover:opacity-80">{initial}</NavLink>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-slate-900">{user?.name || "Learner"}</p>
            <p className="truncate text-[11px] text-slate-500">Ready to keep growing</p>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="app-topbar flex h-[68px] shrink-0 items-center justify-between border-b px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <button type="button" onClick={() => setSidebarOpen((v) => !v)} className="icon-control lg:hidden" aria-label={sidebarOpen ? "Close menu" : "Open menu"}>
              {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Learning space</p>
              <p className="text-sm font-bold text-slate-800">{current.label}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-bold text-amber-700 sm:flex">
              <span className="h-2 w-2 rounded-full bg-amber-400 animate-pulse" /> Keep your streak alive
            </div>
            <NavLink to="/profile" onClick={(event) => handleGuardedNavigate(event, "/profile")} className="flex h-9 w-9 cursor-pointer items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-violet-500 text-xs font-bold text-white transition hover:opacity-80">{initial}</NavLink>
          </div>
        </header>
        <main className="app-main min-w-0 flex-1 overflow-x-hidden overflow-y-auto"><Outlet /></main>
      </div>
    </div>
  );
}
