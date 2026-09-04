const LEVELS = [
  { key: "easy", label: "Easy" },
  { key: "medium", label: "Medium" },
  { key: "hard", label: "Hard" },
];

export default function DifficultySelector({ value, onChange }) {
  return (
    <div className="flex w-full flex-wrap gap-1 rounded-2xl border border-slate-200 bg-white p-1 shadow-sm md:w-auto">
      {LEVELS.map((level) => (
        <button
          key={level.key}
          onClick={() => onChange(level.key)}
          className={`min-h-11 flex-1 rounded-xl px-4 py-2 text-sm font-semibold transition md:flex-none ${
            value === level.key
              ? "bg-brand-50 text-brand-700 shadow-sm"
              : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"
          }`}
        >
          {level.label}
        </button>
      ))}
    </div>
  );
}
