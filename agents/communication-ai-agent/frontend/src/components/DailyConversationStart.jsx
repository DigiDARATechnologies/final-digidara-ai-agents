export default function DailyConversationStart({ vocabulary, loading, onStart }) {
  return (
    <section className="mt-6 rounded-3xl border border-brand-100 bg-gradient-to-b from-white to-brand-50/30 p-6 shadow-soft sm:p-8">
      <div className="mx-auto max-w-xl text-center">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-brand-600">Today's Practice</p>
        <h2 className="mt-2 text-2xl font-extrabold tracking-tight text-slate-900">Daily Speaking Challenge</h2>
        <p className="mt-3 text-sm leading-6 text-slate-500">Talk naturally with your AI conversation partner.</p>
        <div className="mt-7 grid gap-3 text-left sm:grid-cols-2">
          <div className="rounded-2xl bg-brand-50 p-4"><p className="text-xs font-bold uppercase tracking-wide text-brand-600">Practice</p><p className="mt-1 text-sm font-bold text-slate-800">20 everyday conversation questions</p></div>
          <div className="rounded-2xl bg-slate-50 p-4"><p className="text-xs font-bold uppercase tracking-wide text-slate-500">Estimated time</p><p className="mt-1 text-sm font-bold text-slate-800">10–15 minutes</p></div>
        </div>
        <div className="mt-5 text-left">
          <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Today's vocabulary</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {(vocabulary?.length ? vocabulary : ["productive", "catch up", "schedule"]).map((word) => <span key={word} className="rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-bold text-emerald-700">{word}</span>)}
          </div>
        </div>
        <button type="button" onClick={onStart} disabled={loading} className="mt-8 w-full rounded-xl bg-gradient-to-r from-brand-500 to-violet-500 py-3.5 text-sm font-extrabold text-white shadow-lg shadow-brand-500/20 transition hover:from-brand-600 hover:to-violet-600 disabled:cursor-not-allowed disabled:opacity-60">
          {loading ? "Starting Daily Speaking Challenge..." : "Start Daily Speaking Challenge"}
        </button>
      </div>
    </section>
  );
}
