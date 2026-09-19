import React from "react";

/**
 * Compact metric tile for dashboard summaries.
 * @param {{ value: React.ReactNode, label: string, icon?: React.ComponentType, unit?: string, caption?: string }} props
 */
export default function StatBox({ value, label, icon: IconComponent, unit, caption }) {
  return (
    <div className="stat-box">
      {IconComponent && (
        <span className="stat-icon" aria-hidden="true">
          <IconComponent size={20} strokeWidth={2} />
        </span>
      )}
      <span className="stat-num">
        {value}
        {unit && <small>{unit}</small>}
      </span>
      <span className="stat-label">{label}</span>
      {caption && <p className="stat-caption">{caption}</p>}
    </div>
  );
}
