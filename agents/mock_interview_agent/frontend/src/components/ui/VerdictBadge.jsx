import React from "react";
import { VERDICT_ICONS } from "../../utils/icons";
import { VERDICT_LABELS } from "../../utils/verdict";

/**
 * Displays a per-question evaluation verdict and its short explanation.
 * @param {{ verdict?: "correct" | "partial" | "wrong" | null, reason?: string | null }} props
 */
export default function VerdictBadge({ verdict, reason }) {
  if (!VERDICT_LABELS[verdict]) return null;
  const VerdictIcon = VERDICT_ICONS[verdict];

  return (
    <div
      className={`verdict-badge verdict-${verdict}`}
      role="status"
      aria-label={`Answer verdict: ${VERDICT_LABELS[verdict]}`}
    >
      <span className="verdict-icon" aria-hidden="true">
        <VerdictIcon size={18} strokeWidth={2} />
      </span>
      <span className="verdict-label">{VERDICT_LABELS[verdict]}</span>
      {reason && <p className="verdict-reason">{reason}</p>}
    </div>
  );
}
