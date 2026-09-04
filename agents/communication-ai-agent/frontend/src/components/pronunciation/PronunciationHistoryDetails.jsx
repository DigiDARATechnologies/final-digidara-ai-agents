import PronunciationScoreCard from "./PronunciationScoreCard.jsx";
import WordComparison from "./WordComparison.jsx";

export default function PronunciationHistoryDetails({ detail }) {
  if (!detail) return null;
  const result = {
    match_percentage: detail.match_percentage,
    scores: detail.scores,
    expected_text: detail.reference_text,
    recognised_text: detail.recognised_text,
    word_results: detail.word_results,
    correct_words: detail.correct_words,
    missing_words: detail.missing_words,
    different_words: detail.different_words,
    extra_words: detail.extra_words,
    feedback: detail.feedback,
  };
  const feedback = detail.feedback || {};

  return (
    <div className="space-y-4">
      <PronunciationScoreCard result={result} />
      <div className="grid gap-3 md:grid-cols-2">
        <Block title="Reference Text">{detail.reference_text}</Block>
        <Block title="Recognised Text">{detail.recognised_text}</Block>
        <Block title="Assessment Type">{detail.assessment_type}</Block>
        <Block title="Reference Locale">{detail.reference_locale || "Browser default"}</Block>
      </div>
      <WordComparison result={result} />
      <section className="rounded-2xl border border-emerald-100 bg-emerald-50 p-4">
        <h3 className="text-sm font-bold text-emerald-800">Feedback</h3>
        <p className="mt-2 text-sm text-slate-700">{feedback.feedback || "No feedback is available for this attempt."}</p>
        {feedback.practice_tip && (
          <p className="mt-2 rounded-xl bg-white p-3 text-sm text-slate-700">
            <span className="font-bold">Practice Tip: </span>
            {feedback.practice_tip}
          </p>
        )}
      </section>
    </div>
  );
}

function Block({ title, children }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-bold uppercase text-slate-500">{title}</p>
      <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{children || "None"}</p>
    </div>
  );
}
