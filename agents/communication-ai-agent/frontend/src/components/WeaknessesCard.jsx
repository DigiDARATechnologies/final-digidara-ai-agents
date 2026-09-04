export default function WeaknessesCard({ items = [] }) {
  return (
    <section className="rounded-2xl border border-amber-100 bg-amber-50 p-4" aria-labelledby="improve-title">
      <h2 id="improve-title" className="text-sm font-bold text-amber-900">
        Areas to Improve
      </h2>
      {items.length ? (
        <ul className="mt-3 space-y-2 text-sm text-amber-950">
          {items.slice(0, 5).map((item, index) => (
            <li key={`${item}-${index}`} className="rounded-xl bg-white px-3 py-2">
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-amber-950">Detailed improvement areas are unavailable for this session.</p>
      )}
    </section>
  );
}
