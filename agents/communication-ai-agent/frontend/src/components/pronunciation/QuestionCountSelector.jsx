const COUNTS = [
  { key: 5, label: "5 Questions" },
  { key: 10, label: "10 Questions" },
];

export default function QuestionCountSelector({ value, onChange }) {
  return (
    <div className="flex w-full flex-wrap gap-1 rounded-xl bg-slate-100 p-1 md:w-auto">
      {COUNTS.map((count) => (
        <button
          key={count.key}
          onClick={() => onChange(count.key)}
          className={`min-h-11 flex-1 rounded-lg px-4 py-2 text-sm font-semibold transition md:flex-none ${
            value === count.key
              ? "bg-white text-brand-700 shadow-sm"
              : "text-slate-500 hover:text-slate-700"
          }`}
        >
          {count.label}
        </button>
      ))}
    </div>
  );
}
