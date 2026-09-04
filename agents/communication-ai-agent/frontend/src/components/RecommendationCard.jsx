export default function RecommendationCard({ recommendation, nextPractice }) {
  if (!recommendation && !nextPractice) return null;

  return (
    <section className="rounded-2xl border border-brand-100 bg-brand-50 p-4" aria-labelledby="recommendation-title">
      <h2 id="recommendation-title" className="text-sm font-bold text-brand-800">
        Teacher Recommendation
      </h2>
      {recommendation && <p className="mt-2 text-sm text-slate-700">{recommendation}</p>}
      {nextPractice && (
        <div className="mt-3 rounded-xl bg-white p-3">
          <p className="text-xs font-bold uppercase text-slate-500">Suggested Next Practice</p>
          <p className="mt-1 text-sm text-slate-700">{nextPractice}</p>
        </div>
      )}
    </section>
  );
}
