import { useState } from "react";
import { formatScore10 } from "../utils/scoreFormat.js";
import AnswerStatusBadge from "./AnswerStatusBadge.jsx";
import CorrectionBlock from "./CorrectionBlock.jsx";

function normalizeTurn(turn, type) {
  const feedback = turn?.feedback_json || turn?.feedback || {};
  const feedbackObject = typeof feedback === "object" && feedback !== null ? feedback : {};
  const scores = turn?.scores || feedbackObject.scores || {};
  return {
    number: turn?.question_number || turn?.turn_number,
    question: turn?.question || turn?.ai_question || turn?.ai_prompt,
    answer: turn?.user_answer || turn?.user_response,
    answerTimeSeconds: turn?.answer_time_seconds,
    status: turn?.status || turn?.answer_status || feedbackObject.status,
    corrected: turn?.corrected_answer || feedbackObject.corrected_answer,
    explanation: turn?.explanation || feedbackObject.explanation,
    better: turn?.better_natural_answer || feedbackObject.better_natural_answer,
    mistakes: turn?.mistakes || feedbackObject.mistakes || [],
    vocabulary: turn?.vocabulary_suggestions || feedbackObject.vocabulary_suggestions || [],
    scores: {
      confidence: scores.confidence ?? turn?.confidence_score,
      fluency: scores.fluency ?? turn?.fluency_score,
      grammar: scores.grammar ?? turn?.grammar_score,
      vocabulary: scores.vocabulary ?? turn?.vocabulary_score,
      clarity: scores.clarity ?? turn?.clarity_score,
      spelling: scores.spelling,
      relevance: scores.relevance,
      knowledge: scores.knowledge ?? turn?.knowledge_score,
      overall: scores.overall ?? turn?.overall_score,
    },
    type,
  };
}

function formatDurationLabel(seconds) {
  const safeSeconds = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(safeSeconds / 60);
  const remaining = safeSeconds % 60;
  if (!minutes) return `${remaining}s`;
  if (!remaining) return `${minutes}m`;
  return `${minutes}m ${remaining}s`;
}

function scoreEntries(review) {
  const base =
    review.type === "writing"
      ? [
          ["Grammar", review.scores.grammar],
          ["Vocabulary", review.scores.vocabulary],
          ["Clarity", review.scores.clarity],
          ["Spelling", review.scores.spelling],
        ]
      : [
          ["Confidence", review.scores.confidence],
          ["Fluency", review.scores.fluency],
          ["Grammar", review.scores.grammar],
          ["Clarity", review.scores.clarity],
        ];
  return [...base, ["Knowledge", review.scores.knowledge], ["Overall", review.scores.overall]].filter(([, value]) => value != null);
}

export default function QuestionReviewCard({ turn, type, defaultOpen = false, onRetry }) {
  const [open, setOpen] = useState(defaultOpen);
  const review = normalizeTurn(turn, type);
  const needsRetry = !["Correct", "Mostly Correct"].includes(review.status);

  return (
    <article className="rounded-2xl border border-slate-200 bg-white">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 rounded-2xl p-4 text-left outline-none focus-visible:ring-2 focus-visible:ring-brand-300"
      >
        <div>
          <h3 className="text-sm font-bold text-slate-900">Question {review.number || ""}</h3>
          <p className="mt-1 line-clamp-2 text-sm text-slate-500">{review.question || "Question is unavailable."}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <AnswerStatusBadge status={review.status} />
          <span className="text-slate-400" aria-hidden="true">
            {open ? "▲" : "▼"}
          </span>
        </div>
      </button>

      {open && (
        <div className="space-y-3 border-t border-slate-100 p-4">
          <CorrectionBlock title="AI Question">{review.question || "Question is unavailable."}</CorrectionBlock>
          <CorrectionBlock title="Your Answer" empty="No answer was submitted.">
            {review.answer}
          </CorrectionBlock>
          <div>
            <p className="mb-2 text-xs font-bold uppercase text-slate-500">Status</p>
            <div className="flex flex-wrap items-center gap-2">
              <AnswerStatusBadge status={review.status} />
              {review.type === "speaking" && review.answerTimeSeconds ? (
                <span className="rounded-full bg-brand-50 px-3 py-1 text-xs font-bold text-brand-700">
                  Answer time: {formatDurationLabel(review.answerTimeSeconds)}
                </span>
              ) : null}
            </div>
          </div>
          <CorrectionBlock title="Correct Answer" empty="Detailed correction is not available for this older session.">
            {review.corrected}
          </CorrectionBlock>
          <CorrectionBlock title="Explanation" empty="Detailed explanation is not available for this older session.">
            {review.explanation}
          </CorrectionBlock>
          <CorrectionBlock title="Better Natural Answer" empty="A better natural answer is not available for this older session.">
            {review.better}
          </CorrectionBlock>

          {review.mistakes.length > 0 && (
            <div className="rounded-xl bg-slate-50 p-3">
              <p className="text-xs font-bold uppercase text-slate-500">Mistakes</p>
              <div className="mt-2 space-y-2">
                {review.mistakes.map((mistake, index) => (
                  <div key={`${mistake.incorrect}-${index}`} className="rounded-lg bg-white p-3 text-sm text-slate-700">
                    <p className="font-semibold">
                      {mistake.type || "Mistake"}: {mistake.incorrect || "Issue"} {"->"} {mistake.correct || "Correction"}
                    </p>
                    {mistake.explanation && <p className="mt-1 text-slate-500">{mistake.explanation}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {review.vocabulary.length > 0 && (
            <div className="rounded-xl bg-slate-50 p-3">
              <p className="text-xs font-bold uppercase text-slate-500">Vocabulary Suggestions</p>
              <div className="mt-2 space-y-2">
                {review.vocabulary.map((item, index) => (
                  <div key={`${item.suggestion}-${index}`} className="rounded-lg bg-white p-3 text-sm text-slate-700">
                    <p className="font-semibold">
                      {item.original || "Basic phrase"} {"->"} {item.suggestion || "Better phrase"}
                    </p>
                    {item.example && <p className="mt-1 text-slate-500">{item.example}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-2 text-xs font-semibold">
            {scoreEntries(review).map(([label, value]) => (
              <span key={label} className="rounded-full bg-slate-100 px-3 py-1 text-slate-600" aria-label={`${label} score ${formatScore10(value)}`}>
                {label}: {formatScore10(value)}
              </span>
            ))}
          </div>

          {onRetry && (
            <button
              type="button"
              onClick={() => onRetry(turn)}
              className="rounded-xl border border-brand-200 px-4 py-2 text-sm font-bold text-brand-700 outline-none transition hover:bg-brand-50 focus-visible:ring-2 focus-visible:ring-brand-300"
            >
              {needsRetry ? "Try Again" : "Practise Again"}
            </button>
          )}
        </div>
      )}
    </article>
  );
}
