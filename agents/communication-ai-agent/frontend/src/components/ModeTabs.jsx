export default function ModeTabs({ value, onChange, topicLabel = "Topic-wise", dailyLabel = "Daily Speaking Challenge", tabs }) {
  const items = tabs || [
    { key: "topic", label: topicLabel },
    { key: "daily", label: dailyLabel },
  ];

  return (
    <div className="flex w-full flex-wrap gap-2 rounded-2xl border border-slate-200 bg-white p-1 shadow-sm md:w-auto">
      {items.map((tab) => (
        <button
          key={tab.key}
          onClick={() => onChange(tab.key)}
          className={`min-h-11 min-w-[8rem] flex-1 rounded-xl px-3 py-2.5 text-sm font-semibold transition md:flex-none md:px-4 ${
            value === tab.key
              ? "bg-brand-50 text-brand-700 shadow-sm"
              : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
