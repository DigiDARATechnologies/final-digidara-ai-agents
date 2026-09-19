import React from "react";
import SectionCard from "./ui/SectionCard";
import { VERDICT_ICONS } from "../utils/icons";
import { VERDICT_LABELS, formatMarks } from "../utils/verdict";
import { resolveApiAssetUrl } from "../api";

const CorrectIcon = VERDICT_ICONS.correct;

/**
 * Consolidated marks view: one card per real question, with an optional
 * follow-up nested inside the parent question.
 */
export default function QuestionScorecard({
  scorecard = [],
  totalMarks,
  maxMarks,
}) {
  if (!scorecard.length) return null;

  return (
    <SectionCard
      title="Question Scorecard"
      subtitle="A question-by-question review of your spoken answers."
    >
      <div className="scorecard-total-block">
        <p className="scorecard-total">
          Correct-Answer Score:{" "}
          <strong>{formatMarks(totalMarks)} / {maxMarks}</strong>
        </p>
        <p className="scorecard-total-caption">
          A strict, question-by-question tally — 1 mark for each fully
          correct answer, 0.5 for a partially correct answer, and 0 for a
          wrong or unanswered question. This is separate from the AI
          Assessment Score above, which also considers how clearly and
          confidently you communicated — so the two numbers won&apos;t always
          match.
        </p>
      </div>

      <div className="question-scorecard">
        {scorecard.map((item) => (
          <article
            key={item.question_number}
            className={`question-scorecard-item question-scorecard-${item.verdict || "unrated"}`}
          >
            <div className="question-scorecard-header">
              <span className="question-scorecard-label">
                Question {item.question_number}
              </span>
              <span className="question-scorecard-marks">
                {formatMarks(item.marks)} / 1
              </span>
            </div>

            <p className="question-scorecard-question">{item.question}</p>
            <p className="question-scorecard-answer">
              {item.answer || "No answer given."}
            </p>
            {item.answer_audio_path && (
              <div className="answer-recording">
                <span>Your recording</span>
                <audio
                  controls
                  preload="none"
                  src={resolveApiAssetUrl(item.answer_audio_path)}
                />
              </div>
            )}

            {item.followup && (
              <div className="scorecard-followup">
                <span className="tag-followup">Follow-up</span>
                <p className="question-scorecard-question">
                  {item.followup.question}
                </p>
                <p className="question-scorecard-answer">
                  {item.followup.answer || "No answer given."}
                </p>
                {item.followup.answer_audio_path && (
                  <div className="answer-recording">
                    <span>Your follow-up recording</span>
                    <audio
                      controls
                      preload="none"
                      src={resolveApiAssetUrl(item.followup.answer_audio_path)}
                    />
                  </div>
                )}
              </div>
            )}

            <div
              className={`verdict-badge verdict-${item.verdict}`}
              role="status"
              aria-label={`Answer verdict: ${VERDICT_LABELS[item.verdict] || "Not evaluated"}`}
            >
              <span className="verdict-label">
                {VERDICT_LABELS[item.verdict] || "Not evaluated"}
              </span>
              {item.verdict_reason && (
                <p className="verdict-reason">{item.verdict_reason}</p>
              )}
              {item.followup && (
                <p className="verdict-note">
                  Score based on the follow-up answer.
                </p>
              )}
            </div>

            {item.ideal_answer && (
              <div className="ideal-answer-block">
                <span className="ideal-answer-label">
                  <CorrectIcon size={16} strokeWidth={2} aria-hidden="true" />
                  INTERVIEW RECOMMENDED ANSWER
                </span>
                <p className="ideal-answer-text">{item.ideal_answer}</p>
              </div>
            )}
          </article>
        ))}
      </div>
    </SectionCard>
  );
}
