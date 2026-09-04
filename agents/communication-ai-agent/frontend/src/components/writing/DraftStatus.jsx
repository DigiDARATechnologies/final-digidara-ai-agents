export default function DraftStatus({ status, updatedAt, onSave, onClear, disabled }) {
  const savedLabel = updatedAt ? `Saved ${new Date(updatedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : "Not saved yet";
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase text-slate-500">Draft</p>
          <p className="mt-1 text-sm font-semibold text-slate-700">{status || savedLabel}</p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onSave}
            disabled={disabled}
            className="rounded-lg border border-brand-200 px-3 py-2 text-xs font-bold text-brand-700 transition hover:bg-brand-50 disabled:opacity-50"
          >
            Save Draft
          </button>
          <button
            type="button"
            onClick={onClear}
            disabled={disabled}
            className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600 transition hover:bg-slate-50 disabled:opacity-50"
          >
            Clear Draft
          </button>
        </div>
      </div>
    </section>
  );
}
