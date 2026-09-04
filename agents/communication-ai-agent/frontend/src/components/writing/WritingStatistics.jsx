export default function WritingStatistics({ stats }) {
  const items = [
    ["Words", stats.words],
    ["Characters", stats.characters],
    ["Sentences", stats.sentences],
    ["Paragraphs", stats.paragraphs],
    ["Read Time", `${stats.readingMinutes} min`],
  ];

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-bold uppercase text-slate-500">Live Statistics</p>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
        {items.map(([label, value]) => (
          <div key={label} className="rounded-lg bg-slate-50 p-3">
            <p className="text-lg font-bold text-slate-900">{value}</p>
            <p className="text-xs font-semibold text-slate-500">{label}</p>
          </div>
        ))}
      </div>
      <div className="mt-4">
        <div className="h-2 rounded-full bg-slate-100">
          <div className="h-2 rounded-full bg-brand-600 transition-all" style={{ width: `${stats.progress}%` }} />
        </div>
        <p className="mt-2 text-xs font-semibold text-slate-500">{stats.status}</p>
      </div>
    </section>
  );
}
