export default function DailyQuickFeedback({ feedback, onRetry, retrying = false }) {
  if (!feedback) return null;
  const correctedAnswer =
    feedback.corrected_answer && feedback.corrected_answer !== feedback.submittedAnswer
      ? feedback.corrected_answer
      : "";
  return (
    <div className="text-base leading-relaxed text-slate-900">
      <p>{feedback.reaction || "Nice answer!"}</p>
      {correctedAnswer && (
        <>
          <p className="mt-3 text-xs font-bold uppercase tracking-wide text-slate-500">Natural correction:</p>
          <p className="mt-1">{correctedAnswer}</p>
        </>
      )}
      {feedback.short_tip && (
        <p className="mt-3 text-sm text-slate-600">
          <span className="font-bold text-slate-700">Tip:</span> {feedback.short_tip}
        </p>
      )}
      {feedback.source === "fallback" && <p className="mt-2 text-xs font-semibold text-amber-700">AI feedback is temporarily unavailable. Your answer was saved.</p>}
      {feedback.source === "fallback" && onRetry && feedback.turn_id && <button type="button" onClick={() => onRetry(feedback)} disabled={retrying} className="mt-3 rounded-lg border border-brand-200 bg-white px-3 py-1.5 text-xs font-bold text-brand-700 disabled:opacity-60">{retrying ? "Retrying Feedback..." : "Retry Feedback"}</button>}
    </div>
  );
}
