import React from "react";
import PageHeader from "./ui/PageHeader";
import ScoreBar from "./ui/ScoreBar";
import SectionCard from "./ui/SectionCard";
import QuestionScorecard from "./QuestionScorecard";
import {
  ACTION_ICONS,
  APP_ICONS,
  ROUND_TYPE_ICONS,
  STAT_ICONS,
} from "../utils/icons";
import { AI_ASSESSMENT_CAPTION, HR_ASSESSMENT_CAPTION } from "../utils/verdict";
import { logClientEvent } from "../utils/clientLogger";
import { interviewReportPdfUrl } from "../api";

function parseFeedbackPoints(value) {
  if (Array.isArray(value)) {
    return value.map((point) => String(point).trim()).filter(Boolean);
  }
  if (typeof value !== "string" || !value.trim()) return [];

  const text = value.trim();
  try {
    const parsed = JSON.parse(text);
    if (Array.isArray(parsed)) {
      return parsed.map((point) => String(point).trim()).filter(Boolean);
    }
  } catch (error) {
    // Older interviews stored feedback as a paragraph rather than JSON.
    logClientEvent(
      "debug",
      "legacy_feedback_format_used",
      "Feedback was not JSON; parsing it as legacy paragraph text",
      { error }
    );
  }

  const cleanPoint = (point) => point
    .replace(/^\s*\d+[.)]\s*/, "")
    .replace(/^[\s\-*\u2022]+/, "")
    .trim();
  const lines = text.split(/\r?\n/).map(cleanPoint).filter(Boolean);
  if (lines.length > 1) return lines;

  return (text.match(/[^.!?]+(?:[.!?]+|$)/g) || [text])
    .map(cleanPoint)
    .filter(Boolean);
}

/**
 * Final interview report with scoring and written feedback.
 * @param {{ result: Record<string, number | string>, onDone: () => void, onStartAgain?: () => void }} props
 */
export default function ResultScreen({ result, onDone, onStartAgain, onPracticeWeakTopics }) {
  const score = Number(result.overall_score) || 0;
  const message = score >= 8
    ? "Strong performance. Keep sharpening the details."
    : score >= 6
      ? "Good progress. A few focused improvements will help."
      : "Useful practice round. Review the feedback and try again.";
  const AccuracyIcon = result.round_type === "hr"
    ? ROUND_TYPE_ICONS.hr
    : ROUND_TYPE_ICONS.technical;
  const CommunicationIcon = ROUND_TYPE_ICONS.hr;
  const ConfidenceIcon = ACTION_ICONS.achievement;
  const StrengthIcon = STAT_ICONS.correct;
  const ImprovementIcon = STAT_ICONS.warning;
  const FeedbackIcon = APP_ICONS.brand;
  const scoreAngle = `${Math.max(0, Math.min(10, score)) * 36}deg`;
  const strengthPoints = parseFeedbackPoints(result.strengths);
  const improvementPoints = parseFeedbackPoints(result.weaknesses);
  const weakSubjects = result.subject_breakdown?.weak_subjects || [];

  return (
    <div className="page result-page">
      <section className="result-hero">
        <PageHeader
          eyebrow="Interview completed"
          title="Your Interview Report"
          description={message}
        />
        <div className="overall-score report-score score-summary-card">
          <div className="score-gauge" style={{ "--score-angle": scoreAngle }}>
            <span className="score-summary-value">
              <span className="overall-score-num">{result.overall_score}</span>
              <small className="overall-score-max">/10</small>
            </span>
          </div>
          <span className="score-summary-label">AI Assessment Score</span>
          <p className="score-summary-caption">
            {result.round_type === "hr" ? HR_ASSESSMENT_CAPTION : AI_ASSESSMENT_CAPTION}
          </p>
        </div>
      </section>

      <SectionCard
        className="interview-integrity-section"
        title="Interview Focus"
        subtitle="Focus changes recorded while the interview was active."
      >
        <div className="integrity-summary-row">
          <p>
            <strong>{result.focus_loss_count || 0}</strong> focus-loss events
            {" · "}<strong>{result.focus_loss_total_seconds || 0}s</strong> away
          </p>
          {result.integrity_flagged && (
            <span className="integrity-flag-badge">Integrity Flagged</span>
          )}
        </div>
      </SectionCard>

      <SectionCard className="score-breakdown-section" title="Score Breakdown" subtitle="How your answer quality and delivery were evaluated.">
        <div className="score-breakdown">
          <div className="score-metric-card score-metric-indigo">
            <span className="score-metric-icon" aria-hidden="true">
              <AccuracyIcon size={20} strokeWidth={2} />
            </span>
            <ScoreBar
              label={result.round_type === "hr" ? "Answer Relevance & Judgment" : "Technical Accuracy"}
              value={result.technical_accuracy}
            />
          </div>
          <div className="score-metric-card score-metric-teal">
            <span className="score-metric-icon" aria-hidden="true">
              <CommunicationIcon size={20} strokeWidth={2} />
            </span>
            <ScoreBar label="Communication Clarity" value={result.communication_clarity} />
          </div>
          <div className="score-metric-card score-metric-coral">
            <span className="score-metric-icon" aria-hidden="true">
              <ConfidenceIcon size={20} strokeWidth={2} />
            </span>
            <ScoreBar label="Confidence" value={result.confidence} />
          </div>
        </div>
      </SectionCard>

      <div className="feedback-grid">
        <SectionCard className="strengths" title="Strengths">
          <div className="feedback-card-body">
            <span className="feedback-card-icon" aria-hidden="true">
              <StrengthIcon size={22} strokeWidth={2} />
            </span>
            <ul className="feedback-points">
              {strengthPoints.map((point, index) => (
                <li key={`${index}-${point}`}>
                  <StrengthIcon className="feedback-point-icon" size={17} strokeWidth={2} aria-hidden="true" />
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </div>
        </SectionCard>
        <SectionCard className="weaknesses" title="Areas to Improve">
          <div className="feedback-card-body">
            <span className="feedback-card-icon" aria-hidden="true">
              <ImprovementIcon size={22} strokeWidth={2} />
            </span>
            <ul className="feedback-points">
              {improvementPoints.map((point, index) => (
                <li key={`${index}-${point}`}>
                  <ImprovementIcon className="feedback-point-icon" size={17} strokeWidth={2} aria-hidden="true" />
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </div>
        </SectionCard>
      </div>

      <SectionCard className="detailed-feedback" title="Detailed Feedback">
        <div className="feedback-card-body">
          <span className="feedback-card-icon" aria-hidden="true">
            <FeedbackIcon size={22} strokeWidth={2} />
          </span>
          <p>{result.feedback}</p>
        </div>
      </SectionCard>

      <QuestionScorecard
        scorecard={result.scorecard}
        totalMarks={result.total_marks}
        maxMarks={result.max_marks}
      />

      {weakSubjects.length > 0 && onPracticeWeakTopics && (
        <SectionCard
          className="weak-topic-practice"
          title="Practice weak topics"
          subtitle={`Would you like to practice your weak topics (${weakSubjects.join(", ")})?`}
        >
          <button className="primary-btn" onClick={() => onPracticeWeakTopics(weakSubjects)}>
            Practice Weak Topics
          </button>
        </SectionCard>
      )}

      <div className="result-actions">
        {result.interview_id && (
          <a className="secondary-btn" href={interviewReportPdfUrl(result.interview_id)} download>
            Download PDF
          </a>
        )}
        <button className="secondary-btn" onClick={onDone}>
          Go to Dashboard
        </button>
        {onStartAgain && (
          <button className="primary-btn" onClick={onStartAgain}>
            Start Another Interview
          </button>
        )}
      </div>
    </div>
  );
}
