export default function dailyProgress({ answered = 0, total = 20, vocabularyUsed = [] }) {
  const percent = Math.min(100, (answered / Math.max(1, total)) * 100);
  return (
    <div className="mb-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <div className="flex items-center justify-between text-xs font-bold text-slate-500"><span>Daily Speaking Challenge</span><span>{answered} answered</span></div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-brand-600 transition-all" style={{ width: `${percent}%` }} /></div>
      {vocabularyUsed?.length > 0 && <p className="mt-2 text-[11px] font-semibold text-emerald-700">Vocabulary used: {vocabularyUsed.length}</p>}
    </div>
  );
}
