export default function DailyChallengeCard({ item, currentLine = 0 }) {
  const content = item.content || {};
  const lines = content.practice_lines?.length ? content.practice_lines : (item.text || "").split(/\n+/).filter(Boolean);
  const instructions = content.instructions?.length ? content.instructions : item.metadata?.instructions || [];
  return (
    <section className="overflow-hidden rounded-2xl border border-brand-200 bg-white" aria-labelledby="reference-title">
      <div className="border-b border-brand-100 bg-brand-50 p-5">
        <Header label="Daily Pronunciation Challenge" difficulty={item.difficulty} />
        <p className="mt-4 text-xs font-bold uppercase text-brand-600">Today's Mission</p>
        <h1 id="reference-title" className="mt-1 text-2xl font-bold text-slate-900">
          {content.title || item.metadata?.title || item.meaning || "Daily Pronunciation Challenge"}
        </h1>
        {(content.description || item.metadata?.description) && (
          <p className="mt-2 text-sm text-slate-600">{content.description || item.metadata?.description}</p>
        )}
      </div>

      <div className="space-y-3 p-5">
        <div>
          <p className="text-xs font-bold uppercase text-slate-500">Practice Lines</p>
          <div className="mt-2 space-y-2">
            {lines.map((line, index) => (
              <p
                key={`${line}-${index}`}
                className={`rounded-xl p-3 text-sm font-semibold ${
                  index === currentLine ? "bg-brand-50 text-brand-800" : "bg-slate-50 text-slate-700"
                }`}
              >
                {index + 1}. {line}
              </p>
            ))}
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <InfoList title="Instructions" items={instructions} />
          <InfoBlock title="Goal">{content.goal || item.metadata?.goal || "Speak every line clearly."}</InfoBlock>
        </div>
        <Footer duration={content.expected_duration_seconds || item.expected_duration_seconds} />
      </div>
    </section>
  );
}

function Header({ label, difficulty }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="rounded-full bg-brand-100 px-3 py-1 text-xs font-bold text-brand-700">{label}</span>
      <span className="rounded-full bg-white px-3 py-1 text-xs font-bold capitalize text-slate-600">{difficulty}</span>
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

function InfoList({ title, items = [] }) {
  return (
    <div className="rounded-xl bg-slate-50 p-3">
      <p className="text-xs font-bold uppercase text-slate-500">{title}</p>
      <ul className="mt-1 space-y-1 text-sm text-slate-700">
        {(items.length ? items : ["Listen once.", "Repeat clearly."]).map((item, index) => (
          <li key={`${item}-${index}`}>- {item}</li>
        ))}
      </ul>
    </div>
  );
}

function Footer({ duration }) {
  if (!duration) return null;
  return <p className="text-xs font-medium text-slate-400">Expected speaking duration: about {duration} seconds</p>;
}
