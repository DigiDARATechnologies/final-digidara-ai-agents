import { formatScoreNumber, scoreToTen } from "../utils/scoreFormat.js";

export default function ScoreRing({ score, label, size = 96, stroke = 8 }) {
  const value = scoreToTen(score);
  const displayValue = value ?? 0;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (displayValue / 10) * circumference;

  const color =
    displayValue >= 8 ? "#16a34a" : displayValue >= 6 ? "#3866f5" : displayValue >= 4 ? "#f59e0b" : "#ef4444";

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle cx={size / 2} cy={size / 2} r={radius} stroke="#e2e8f0" strokeWidth={stroke} fill="none" />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={color}
            strokeWidth={stroke}
            fill="none"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={score == null ? circumference : offset}
            style={{ transition: "stroke-dashoffset 0.6s ease" }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-lg font-bold text-slate-800">{formatScoreNumber(score, "-")}</span>
        </div>
      </div>
      {label && <p className="text-xs font-medium text-slate-500">{label}</p>}
    </div>
  );
}
