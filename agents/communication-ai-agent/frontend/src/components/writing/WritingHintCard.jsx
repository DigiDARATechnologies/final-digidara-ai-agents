export default function WritingHintCard({ hint, count, maxHints, loading, onGetHint, error }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase text-slate-500">AI Hints</p>
          <p className="mt-1 text-sm text-slate-600">{count} / {maxHints} used</p>
        </div>
        <button
          type="button"
          onClick={onGetHint}
          disabled={loading}
          className="rounded-lg bg-brand-600 px-3 py-2 text-xs font-bold text-white transition hover:bg-brand-700 disabled:opacity-50"
        >
          {loading ? "Getting..." : "Get AI Hint"}
        </button>
      </div>
      {error && <p className="mt-2 text-xs font-medium text-red-500">{error}</p>}

      {hint ? (
        <div className="mt-4 space-y-3">
          <HintList title="Outline" items={hint.outline} />
          <HintList title="Useful Words" items={hint.useful_words} inline />
          <HintList title="Transitions" items={hint.transition_words} inline />
          <p className="rounded-lg bg-brand-50 p-3 text-sm text-slate-700">{hint.teacher_tip}</p>
        </div>
      ) : (
        <p className="mt-4 text-sm text-slate-500">Ask for a small outline or vocabulary nudge when you are stuck.</p>
      )}
    </section>
  );
}

function HintList({ title, items = [], inline = false }) {
  if (!items.length) return null;
  return (
    <div>
      <p className="text-xs font-bold uppercase text-slate-500">{title}</p>
      <div className={inline ? "mt-2 flex flex-wrap gap-2" : "mt-2 space-y-1"}>
        {items.map((item, index) => (
          <span key={`${item}-${index}`} className={inline ? "rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600" : "block text-sm text-slate-600"}>
            {inline ? item : `- ${item}`}
          </span>
        ))}
      </div>
    </div>
  );
}
