const STYLE = {
  Correct: "border-emerald-200 bg-emerald-50 text-emerald-800",
  Missing: "border-amber-200 bg-amber-50 text-amber-900",
  Different: "border-red-200 bg-red-50 text-red-800",
  Extra: "border-slate-200 bg-slate-50 text-slate-700",
  "Needs Practice": "border-red-200 bg-red-50 text-red-800",
};

export default function WordComparison({ result }) {
  const words = result?.word_results || result?.comparison?.word_results || [];
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5" aria-labelledby="word-comparison-title">
      <h2 id="word-comparison-title" className="text-base font-bold text-slate-900">
        Word-by-Word Result
      </h2>
      <div className="mt-3 flex flex-wrap gap-2">
        {words.length ? (
          words.map((word, index) => (
            <span
              key={`${word.word}-${word.recognised}-${index}`}
              className={`rounded-xl border px-3 py-2 text-xs font-bold ${STYLE[word.status] || STYLE.Extra}`}
              aria-label={`${word.word}, ${word.status}`}
            >
              {word.word}
              {word.recognised && word.recognised !== word.word ? ` -> ${word.recognised}` : ""} - {word.status}
            </span>
          ))
        ) : (
          <p className="text-sm text-slate-500">No word comparison is available.</p>
        )}
      </div>
    </section>
  );
}
