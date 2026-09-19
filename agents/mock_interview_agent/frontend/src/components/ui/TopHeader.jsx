import React from "react";
import { APP_ICONS } from "../../utils/icons";
import StudentAvatar from "./StudentAvatar";

const MenuIcon = APP_ICONS.menu;

/**
 * Main content header with current page title and profile badge.
 * @param {{ title: string, subtitle?: string, onSidebarToggle: () => void, isSidebarCollapsed?: boolean, onNavigate: (screen: string) => void, isInterviewActive?: boolean, studentName: string, studentInitials: string, avatarColor: string, avatarUrl?: string }} props
 */
export default function TopHeader({
  title,
  subtitle,
  onSidebarToggle,
  isSidebarCollapsed,
  onNavigate,
  isInterviewActive,
  studentName,
  studentInitials,
  avatarColor,
  avatarUrl,
}) {
  return (
    <header className="main-header">
      <button
        type="button"
        className="header-sidebar-toggle-btn"
        onClick={onSidebarToggle}
        aria-label={isSidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        aria-expanded={!isSidebarCollapsed}
      >
        <MenuIcon size={20} strokeWidth={2.25} aria-hidden="true" />
      </button>
      <div className="main-header-copy">
        <p className="eyebrow">AI Mock Interview</p>
        <h1>{title}</h1>
        {subtitle && <p className="header-subtitle">{subtitle}</p>}
      </div>
      <button
        type="button"
        className="profile-badge profile-badge-clickable"
        onClick={() => onNavigate?.("profile")}
        disabled={isInterviewActive}
        aria-label="Go to your profile"
      >
        <StudentAvatar
          avatarUrl={avatarUrl}
          initials={studentInitials}
          avatarColor={avatarColor}
        />
        <div>
          <strong>{studentName}</strong>
        </div>
      </button>
    </header>
  );
}
