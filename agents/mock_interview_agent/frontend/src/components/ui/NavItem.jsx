import React from "react";

/**
 * Sidebar/mobile navigation action.
 * @param {{ icon: React.ComponentType, label: string, active?: boolean, disabled?: boolean, onClick: () => void }} props
 */
export default function NavItem({ icon: IconComponent, label, active = false, disabled = false, onClick }) {
  return (
    <button
      type="button"
      className={`nav-item ${active ? "nav-item-active" : ""}`}
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
    >
      <span className="nav-icon" aria-hidden="true">
        <IconComponent size={18} strokeWidth={2} />
      </span>
      <span className="nav-label">{label}</span>
    </button>
  );
}
