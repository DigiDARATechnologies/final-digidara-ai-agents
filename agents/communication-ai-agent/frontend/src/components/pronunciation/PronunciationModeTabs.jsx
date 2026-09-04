import { useEffect, useState } from "react";
import { CalendarCheck2, MessageCircle } from "lucide-react";
import client from "../../api/client";

const MODES = [
  { key: "sentence", label: "Sentence Practice", subtitle: "Full sentences", icon: MessageCircle },
  { key: "daily", label: "Daily Pronunciation Challenge", subtitle: "Today's set", icon: CalendarCheck2 },
];

export default function PronunciationModeTabs({ value, onChange }) {
  const [streak, setStreak] = useState(0);

  useEffect(() => {
    client.get("/pronunciation/streak").then((res) => {
      if (res.data?.streak_count) {
        setStreak(res.data.streak_count);
      }
    }).catch(() => {});
  }, []);

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2" role="tablist" aria-label="Pronunciation practice mode">
      {MODES.map((mode) => {
        const Icon = mode.icon;
        const selected = value === mode.key;
        return (
          <button
            key={mode.key}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(mode.key)}
            className={`learning-card min-h-[150px] p-4 text-left outline-none focus-visible:ring-2 focus-visible:ring-brand-300 ${
              selected ? "border-brand-500 bg-brand-50 ring-2 ring-brand-100" : ""
            }`}
          >
            <div>
              <div className="flex items-start justify-between gap-3">
                <span className="learning-card-icon"><Icon className="h-5 w-5" /></span>
                {selected ? (
                  <span className="learning-badge bg-brand-600 text-white">Selected</span>
                ) : mode.key === "daily" && streak > 0 ? (
                  <span className="learning-badge bg-amber-50 text-amber-700">Streak {streak}</span>
                ) : (
                  <span className="learning-badge">Mode</span>
                )}
              </div>
              <p className="mt-4 text-sm font-bold text-slate-900">{mode.label}</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">{mode.subtitle}</p>
            </div>
          </button>
        );
      })}
    </div>
  );
}
