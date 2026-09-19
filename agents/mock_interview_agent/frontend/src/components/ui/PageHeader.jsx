import React from "react";

/**
 * Section-level page heading with optional action.
 * @param {{ eyebrow?: string, title: string, description?: string, action?: React.ReactNode }} props
 */
export default function PageHeader({ eyebrow, title, description, action }) {
  return (
    <div className="page-header">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {action && <div className="page-header-action">{action}</div>}
    </div>
  );
}
