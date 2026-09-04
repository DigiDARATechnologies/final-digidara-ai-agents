export default function WordPracticeCard({ item }) {
  const content = item.content || {};
  const syllables = content.syllables || [];
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5" aria-labelledby="reference-title">
      <Header label="Word Practice" difficulty={item.difficulty} />
      <p className="mt-4 text-xs font-bold uppercase text-slate-400">Practice Word</p>
      <h1 id="reference-title" className="mt-1 text-4xl font-bold tracking-normal text-slate-900">
        {content.practice_text || item.text}
      </h1>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <InfoBlock title="Meaning">{content.meaning || item.meaning || "Meaning is not available for this word."}</InfoBlock>
        <InfoBlock title="Example Sentence">{content.example_sentence || item.example_sentence || "Example sentence is not available."}</InfoBlock>
        {syllables.length > 0 && <InfoBlock title="Syllables">{syllables.join(" - ")}</InfoBlock>}
        <InfoBlock title="Sound Focus">{item.metadata?.sound_focus || item.metadata?.focus_tip || "Listen, repeat slowly, then say the word naturally."}</InfoBlock>
      </div>
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
