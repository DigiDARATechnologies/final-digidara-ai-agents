export default function TranscriptReview({
  transcript,
  interimTranscript,
  listening,
  unsupported,
  error,
  disabled = false,
  onChange,
  onTry,
  onDone,
  onContinue,
  onRetry,
  onClear,
  onSubmit,
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4" aria-labelledby="recorder-title">
      <h2 id="recorder-title" className="text-sm font-bold text-slate-900">
        Try Pronunciation
      </h2>
      <p className="mt-1 text-xs text-slate-500" aria-live="polite">
        {listening ? "Listening... Please repeat the sentence." : "Review the transcript before submitting."}
      </p>
      {unsupported && (
        <p className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-800">
          Speech Recognition is not supported in this browser. You can type what you spoke for basic flow testing.
        </p>
      )}
      {error && <p className="mt-3 rounded-xl bg-red-50 p-3 text-sm font-medium text-red-700">{error}</p>}
      {interimTranscript && (
        <p className="mt-3 rounded-xl bg-brand-50 p-3 text-sm text-brand-700">Interim: {interimTranscript}</p>
      )}
      <label htmlFor="pronunciation-transcript" className="mt-4 block text-xs font-bold uppercase text-slate-500">
        Recognised Answer
      </label>
      <textarea
        id="pronunciation-transcript"
        value={transcript}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        rows={4}
        className="mt-2 w-full resize-none rounded-xl border border-slate-200 p-3 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100 disabled:bg-slate-50 disabled:opacity-60"
        placeholder="Your recognised speech will appear here..."
      />
      <div className="mt-3 flex flex-wrap gap-2">
        <button onClick={onTry} disabled={disabled || listening} className="rounded-xl bg-brand-600 px-4 py-2 text-sm font-bold text-white disabled:opacity-50">
          Try Pronunciation
        </button>
        <button onClick={onDone} disabled={disabled || !listening} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-600 disabled:opacity-50">
          I'm Done Speaking
        </button>
        <button onClick={onContinue} disabled={disabled || listening} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-600 disabled:opacity-50">
          Continue Speaking
        </button>
        <button onClick={onRetry} disabled={disabled} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-600 disabled:opacity-50">
          Retry Recording
        </button>
        <button onClick={onClear} disabled={disabled} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-600 disabled:opacity-50">
          Clear
        </button>
        <button onClick={onSubmit} disabled={disabled || !transcript.trim()} className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-bold text-white disabled:opacity-50">
          Submit Pronunciation
        </button>
      </div>
    </section>
  );
}
