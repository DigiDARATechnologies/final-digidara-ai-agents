import React from "react";

/**
 * Horizontal score meter for interview scoring metrics.
 * @param {{ label: string, value?: number | string, max?: number }} props
 */
export default function ScoreBar({ label, value = 0, max = 10 }) {
  const numericValue = Number(value) || 0;
  const percent = Math.max(0, Math.min(100, (numericValue / max) * 100));

  return (
    <div className="score-row">
      <div className="score-row-top">
        <span>{label}</span>
        <span>{value ?? "-"}/{max}</span>
      </div>
      <div className="score-track" aria-hidden="true">
        <div className="score-fill" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}
