import { useState } from "react";

/** One series of daily counts as columns, with a hover readout. */
export function ColumnTrend({ points, label }: { points: { date: string; value: number }[]; label: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(1, ...points.map((p) => p.value));
  const active = hover === null ? null : points[hover];
  return (
    <figure className="org-trend" aria-label={label}>
      <div className="org-trend-readout" aria-live="polite">
        {active ? <><b>{active.value}</b> on {new Date(`${active.date}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" })}</>
          : <><b>{points.at(-1)?.value ?? 0}</b> today</>}
      </div>
      <div className="org-trend-cols" onMouseLeave={() => setHover(null)}>
        {points.map((point, index) => (
          <button key={point.date} type="button" className={`org-trend-col${hover === index ? " on" : ""}`}
            onMouseEnter={() => setHover(index)} onFocus={() => setHover(index)} onBlur={() => setHover(null)}
            aria-label={`${point.date}: ${point.value}`}>
            <span style={{ height: `${Math.max(point.value ? 6 : 2, (point.value / max) * 100)}%` }} />
          </button>
        ))}
      </div>
      <figcaption className="org-trend-axis">
        <span>{points[0] ? new Date(`${points[0].date}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" }) : ""}</span>
        <span>Today</span>
      </figcaption>
    </figure>
  );
}

/** Labelled horizontal bars for one measure (one accent color). */
export function BarList({ rows, max: fixedMax, format = (v) => String(v), onSelect }: {
  rows: { key: string; label: string; value: number | null; note?: string }[];
  max?: number;
  format?: (value: number) => string;
  onSelect?: (key: string) => void;
}) {
  const max = fixedMax ?? Math.max(1, ...rows.map((r) => r.value ?? 0));
  if (!rows.length) return <p className="rd-muted">Nothing to show yet.</p>;
  return (
    <ul className="org-barlist">
      {rows.map((row) => {
        const content = (
          <>
            <span className="org-bar-label">{row.label}{row.note && <small>{row.note}</small>}</span>
            <span className="org-bar-track"><i style={{ width: `${row.value === null ? 0 : Math.max(2, (row.value / max) * 100)}%` }} /></span>
            <b className="org-bar-value">{row.value === null ? "–" : format(row.value)}</b>
          </>
        );
        return (
          <li key={row.key} title={`${row.label}: ${row.value === null ? "no data" : format(row.value)}`}>
            {onSelect ? <button type="button" className="org-bar-row" onClick={() => onSelect(row.key)}>{content}</button>
              : <div className="org-bar-row">{content}</div>}
          </li>
        );
      })}
    </ul>
  );
}

/** Ordered levels as one-hue steps, light (Beginner) to dark (Professional). */
export const LEVEL_ORDER = ["beginner", "medium", "hard", "professional"] as const;

export function LevelStacks({ rows, labels }: {
  rows: { key: string; label: string; counts: Record<string, number> }[];
  labels: Record<string, string>;
}) {
  return (
    <div className="org-stacks">
      {rows.map((row) => {
        const total = LEVEL_ORDER.reduce((sum, level) => sum + (row.counts[level] ?? 0), 0);
        return (
          <div key={row.key} className="org-stack-row">
            <span className="org-bar-label">{row.label}</span>
            <div className="org-stack" role="img" aria-label={`${row.label}: ${LEVEL_ORDER.map((l) => `${labels[l]} ${row.counts[l] ?? 0}`).join(", ")}`}>
              {total === 0 ? <i className="org-stack-empty" /> : LEVEL_ORDER.map((level) => (row.counts[level] ?? 0) > 0 && (
                <i key={level} className={`org-lv org-lv-${level}`} style={{ flexGrow: row.counts[level] }}
                  title={`${labels[level]}: ${row.counts[level]}`}>
                  {row.counts[level]}
                </i>
              ))}
            </div>
          </div>
        );
      })}
      <div className="org-legend">
        {LEVEL_ORDER.map((level) => <span key={level}><i className={`org-lv org-lv-${level}`} />{labels[level]}</span>)}
      </div>
    </div>
  );
}
