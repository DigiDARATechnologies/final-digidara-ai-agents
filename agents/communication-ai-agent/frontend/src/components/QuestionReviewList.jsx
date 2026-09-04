import QuestionReviewCard from "./QuestionReviewCard.jsx";

export default function QuestionReviewList({ turns = [], type, onRetry }) {
  if (!turns.length) {
    return (
      <section className="rounded-2xl border border-slate-200 bg-white p-4">
        <h2 className="text-base font-bold text-slate-900">Question-by-Question Review</h2>
        <p className="mt-2 text-sm text-slate-500">No answered questions are available for this session.</p>
      </section>
    );
  }

  return (
    <section aria-labelledby="question-review-title">
      <h2 id="question-review-title" className="text-base font-bold text-slate-900">
        Question-by-Question Review
      </h2>
      <div className="mt-3 space-y-3">
        {turns.map((turn, index) => (
          <QuestionReviewCard
            key={`${turn.turn_number || index}-${turn.ai_question || turn.ai_prompt || index}`}
            turn={turn}
            type={type}
            defaultOpen={index === 0}
            onRetry={onRetry}
          />
        ))}
      </div>
    </section>
  );
}
