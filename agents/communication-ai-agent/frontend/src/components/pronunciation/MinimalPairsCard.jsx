export default function MinimalPairsCard({ item }) {
  const meta = item.metadata || {};
  const { pair, target_word, title } = meta;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5" aria-labelledby="reference-title">
      <Header label="Minimal Pairs" difficulty={item.difficulty} />
      
      <p className="mt-4 text-xs font-bold uppercase text-slate-400">{title || "Practice Pair"}</p>
      
      <div className="mt-4 flex items-center justify-center gap-8">
        {pair && pair.map((word, idx) => (
          <div 
            key={idx}
            className={`flex h-24 w-40 flex-col items-center justify-center rounded-2xl border-2 transition ${
              word === target_word 
                ? "border-brand-500 bg-brand-50 text-brand-700 shadow-sm" 
                : "border-slate-100 bg-slate-50 text-slate-400 opacity-60"
            }`}
          >
            <span className="text-3xl font-bold tracking-tight">{word}</span>
            {word === target_word && <span className="mt-1 text-xs font-semibold uppercase">Target</span>}
          </div>
        ))}
      </div>
      
      <div className="mt-6 grid gap-3 md:grid-cols-2">
        <InfoBlock title="Meaning">{item.meaning || "Meaning is not available."}</InfoBlock>
        <InfoBlock title="Tip">Pay close attention to the subtle differences in pronunciation between the two words.</InfoBlock>
      </div>
    </section>
  );
}

function Header({ label, difficulty }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="rounded-full bg-brand-50 px-3 py-1 text-xs font-bold text-brand-700">{label}</span>
      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold capitalize text-slate-600">{difficulty}</span>
    </div>
  );
}

function InfoBlock({ title, children }) {
  return (
    <div className="rounded-xl bg-slate-50 p-3">
      <p className="text-xs font-bold uppercase text-slate-500">{title}</p>
      <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{children}</p>
    </div>
  );
}
