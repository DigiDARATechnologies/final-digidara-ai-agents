export default function SentencePracticeCard({ item }) {
  const content = item.content || {};
  const metadata = item.metadata || {};
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5" aria-labelledby="reference-title">
      <Header label="Sentence Practice" difficulty={item.difficulty} />
      <p className="mt-4 text-xs font-bold uppercase text-slate-400">Reference Sentence</p>
      <h1 id="reference-title" className="mt-1 text-2xl font-bold leading-snug text-slate-900">
        {content.practice_text || item.text}
      </h1>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <InfoBlock title="Speaking Goal">{metadata.speaking_goal || "Say the full sentence clearly and naturally."}</InfoBlock>
        <InfoBlock title="Focus Tip">{metadata.focus_tip || "Keep every important word clear."}</InfoBlock>
      </div>
      {metadata.difficult_words?.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-bold uppercase text-slate-400">Difficult Words</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {metadata.difficult_words.map((word) => (
              <span key={word} className="rounded-full bg-amber-50 px-3 py-1 text-xs font-bold text-amber-800">
                {word}
              </span>
            ))}
          </div>
        </div>
      )}
      <Footer duration={content.expected_duration_seconds || item.expected_duration_seconds} />
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

function Footer({ duration }) {
  if (!duration) return null;
  return <p className="mt-4 text-xs font-medium text-slate-400">Expected speaking duration: about {duration} seconds</p>;
}
