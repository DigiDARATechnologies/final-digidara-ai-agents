import React from "react";

/**
 * Friendly empty-state panel with a subtle CSS illustration.
 * @param {{ title: string, message: string, action?: React.ReactNode }} props
 */
export default function EmptyState({ title, message, action }) {
  return (
    <div className="empty-state">
      <div className="empty-illustration" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <h3>{title}</h3>
      <p className="subtle">{message}</p>
      {action && <div className="empty-action">{action}</div>}
    </div>
  );
}
