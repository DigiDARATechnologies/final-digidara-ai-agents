export default function StrengthsCard({ items = [] }) {
  return (
    <section className="rounded-2xl border border-emerald-100 bg-emerald-50 p-4" aria-labelledby="strengths-title">
      <h2 id="strengths-title" className="text-sm font-bold text-emerald-800">
        Your Strengths
      </h2>
      {items.length ? (
        <ul className="mt-3 space-y-2 text-sm text-emerald-900">
          {items.slice(0, 5).map((item, index) => (
            <li key={`${item}-${index}`} className="rounded-xl bg-white px-3 py-2">
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-emerald-900">Detailed strengths are unavailable for this session.</p>
      )}
    </section>
  );
}
