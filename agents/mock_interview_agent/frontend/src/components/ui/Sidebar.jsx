import React from "react";
import NavItem from "./NavItem";
import StudentAvatar from "./StudentAvatar";
import { APP_ICONS, NAV_ICONS } from "../../utils/icons";

const CloseIcon = APP_ICONS.close;

/**
 * Persistent app navigation for desktop and drawer navigation for mobile.
 * @param {{ screen: string, isOpen: boolean, isCollapsed: boolean, isInterviewActive: boolean, onNavigate: (screen: string) => void, onClose: () => void, studentName: string, studentInitials: string, avatarColor: string, avatarUrl?: string }} props
 */
export default function Sidebar({
  screen,
  isOpen,
  isCollapsed,
  isInterviewActive,
  onNavigate,
  onClose,
  studentName,
  studentInitials,
  avatarColor,
  avatarUrl,
}) {
  const navItems = [
    { key: "dashboard", label: "Dashboard", icon: NAV_ICONS.dashboard },
    { key: "setup", label: "New Interview", icon: NAV_ICONS.setup },
    { key: "history", label: "Interview History", icon: NAV_ICONS.history },
    { key: "analytics", label: "AI Usage", icon: NAV_ICONS.dashboard },
    { key: "profile", label: "Profile", icon: NAV_ICONS.profile },
  ];

  function handleNavigate(nextScreen) {
    onNavigate(nextScreen);
    onClose();
  }

  return (
    <>
      <aside className={`sidebar ${isOpen ? "sidebar-open" : ""} ${isCollapsed ? "sidebar-collapsed" : ""}`}>
        <button
          type="button"
          className="sidebar-close-btn"
          onClick={onClose}
          aria-label="Close menu"
        >
          <CloseIcon size={20} strokeWidth={2} aria-hidden="true" />
        </button>
        <div className="sidebar-brand">
          <img className="brand-logo" src="/logo.png" alt="" aria-hidden="true" />
          <div className="sidebar-brand-copy">
            <strong>AI Mock Interview</strong>
            <span>Practice. Improve. Succeed.</span>
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="Main navigation">
          {navItems.map((item) => (
            <NavItem
              key={item.key}
              icon={item.icon}
              label={item.label}
              active={screen === item.key}
              disabled={isInterviewActive}
              onClick={() => handleNavigate(item.key)}
            />
          ))}
        </nav>

        {isInterviewActive && (
          <p className="sidebar-note">
            Finish or exit the active interview before switching pages.
          </p>
        )}

        <button
          type="button"
          className="sidebar-profile sidebar-profile-clickable"
          onClick={() => handleNavigate("profile")}
          disabled={isInterviewActive}
          aria-label="Go to your profile"
        >
          <StudentAvatar
            className="avatar"
            avatarUrl={avatarUrl}
            initials={studentInitials}
            avatarColor={avatarColor}
          />
          <div className="sidebar-profile-copy">
            <strong>{studentName}</strong>
          </div>
        </button>
      </aside>
      {isOpen && <button className="sidebar-backdrop" type="button" aria-label="Close menu" onClick={onClose} />}
    </>
  );
}
