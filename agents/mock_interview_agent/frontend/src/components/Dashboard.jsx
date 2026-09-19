import React, { useCallback, useEffect, useState } from "react";
import { getDashboard } from "../api";
import { ACTION_ICONS, NAV_ICONS, STAT_ICONS } from "../utils/icons";
import { reportClientError } from "../utils/clientLogger";
import EmptyState from "./ui/EmptyState";
import Pill from "./ui/Pill";
import SectionCard from "./ui/SectionCard";
import Skeleton, { SkeletonStack } from "./ui/Skeleton";
import StatBox from "./ui/StatBox";

const StartIcon = NAV_ICONS.setup;
const CHART_SERIES = [
  { key: "overall_score", label: "Overall", color: "#2563eb" },
  { key: "technical_accuracy", label: "Technical", color: "#0891b2" },
  { key: "communication_clarity", label: "Communication", color: "#7c3aed" },
  { key: "confidence", label: "Confidence", color: "#d97706" },
];

function formatLabel(value) {
  if (!value) return "—";
  return value
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function metricValue(value) {
  return value == null ? "No data yet" : value;
}

function SkillPerformanceChart({ points }) {
  const usableSeries = CHART_SERIES.filter((series) => (
    points.some((point) => point[series.key] != null)
  ));
  if (!points.length || !usableSeries.length) {
    return (
      <p className="subtle dashboard-empty-copy">
        Complete a scored interview to see your skill trend.
      </p>
    );
  }

  const width = 720;
  const height = 280;
  const left = 42;
  const right = 18;
  const top = 16;
  const bottom = 42;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const x = (index) => (
    left + (points.length === 1 ? plotWidth / 2 : (index / (points.length - 1)) * plotWidth)
  );
  const y = (value) => top + ((10 - value) / 10) * plotHeight;

  return (
    <div className="skill-chart-shell">
      <div className="skill-chart-legend" aria-label="Chart legend">
        {usableSeries.map((series) => (
          <span key={series.key}>
            <i style={{ backgroundColor: series.color }} />
            {series.label}
          </span>
        ))}
      </div>
      <svg
        className="skill-chart"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Skill scores across recent completed interviews, on a zero to ten scale"
      >
        <title>Recent skill performance trend</title>
        {[0, 2, 4, 6, 8, 10].map((tick) => (
          <g key={tick}>
            <line
              x1={left}
              x2={width - right}
              y1={y(tick)}
              y2={y(tick)}
              className="skill-chart-gridline"
            />
            <text x={left - 10} y={y(tick) + 4} className="skill-chart-axis" textAnchor="end">
              {tick}
            </text>
          </g>
        ))}
        {usableSeries.map((series) => {
          const seriesPoints = points
            .map((point, index) => (
              point[series.key] == null ? null : `${x(index)},${y(point[series.key])}`
            ))
            .filter(Boolean);
          return (
            <g key={series.key}>
              {seriesPoints.length > 1 && (
                <polyline
                  points={seriesPoints.join(" ")}
                  fill="none"
                  stroke={series.color}
                  strokeWidth="3"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              )}
              {points.map((point, index) => (
                point[series.key] == null ? null : (
                  <circle
                    key={`${series.key}-${point.id}`}
                    cx={x(index)}
                    cy={y(point[series.key])}
                    r="4"
                    fill={series.color}
                  >
                    <title>
                      {series.label}: {point[series.key]}/10 on {point.date}
                    </title>
                  </circle>
                )
              ))}
            </g>
          );
        })}
        {points.map((point, index) => (
          <text
            key={point.id}
            x={x(index)}
            y={height - 14}
            className="skill-chart-axis"
            textAnchor="middle"
          >
            {point.date?.slice(5) || `#${index + 1}`}
          </text>
        ))}
      </svg>
    </div>
  );
}

/**
 * Performance dashboard for aggregate interview history.
 * @param {{
 *   studentId: number,
 *   studentName?: string,
 *   onStartInterview: () => void,
 *   onViewInterview: (id: number) => void
 * }} props
 */
export default function Dashboard({
  studentId,
  studentName = "",
  onStartInterview,
  onViewInterview,
}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadDashboard = useCallback(async () => {
    // Let the current render commit before beginning this external data sync.
    await Promise.resolve();
    setLoading(true);
    setError(null);
    try {
      setData(await getDashboard(studentId));
    } catch (e) {
      reportClientError("dashboard_load_failed", e, { student_id: studentId });
      setError(e.message || "Unable to load dashboard data. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [studentId]);

  useEffect(() => {
    let isMounted = true;
    getDashboard(studentId)
      .then((dashboardData) => {
        if (isMounted) setData(dashboardData);
      })
      .catch((requestError) => {
        reportClientError("dashboard_load_failed", requestError, {
          student_id: studentId,
        });
        if (isMounted) {
          setError(
            requestError.message
            || "Unable to load dashboard data. Please try again."
          );
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, [studentId]);

  const personalizedHeading = studentName
    ? `Welcome back, ${studentName}!`
    : "Welcome back!";

  if (loading) {
    return (
      <div className="page dashboard-page">
        <section className="dashboard-hero skeleton-hero">
          <Skeleton className="skeleton-line skeleton-line-wide" />
          <Skeleton className="skeleton-line skeleton-line-short" />
        </section>
        <div className="stat-grid dashboard-stat-grid">
          {Array.from({ length: 8 }, (_, index) => (
            <Skeleton key={index} className="stat-skeleton" />
          ))}
        </div>
        <SkeletonStack rows={3} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="page dashboard-page">
        <SectionCard className="dashboard-state dashboard-error">
          <p className="error-text" role="alert">{error}</p>
          <button className="secondary-btn" onClick={loadDashboard}>Retry</button>
        </SectionCard>
      </div>
    );
  }

  if (!data || data.total_interviews === 0) {
    return (
      <div className="page dashboard-page">
        <section className="dashboard-hero">
          <div>
            <h2>{personalizedHeading}</h2>
            <p>Start your first session to unlock real score trends, history, and personalized recommendations.</p>
          </div>
          <button className="primary-btn hero-action" onClick={onStartInterview}>
            <StartIcon className="button-icon" size={18} strokeWidth={2} /> Start New Interview
          </button>
        </section>
        <EmptyState
          title="No interviews completed yet"
          message="Complete your first mock interview to view dashboard insights based on your results."
          action={(
            <button className="primary-btn" onClick={onStartInterview}>
              <StartIcon className="button-icon" size={18} strokeWidth={2} /> Start New Interview
            </button>
          )}
        />
      </div>
    );
  }

  const improvement = data.improvement || {};
  const recommendation = data.recommended_next_interview;
  const recentInterviews = data.recent_interviews || [];
  const trend = data.skill_performance_trend || [];

  return (
    <div className="page dashboard-page">
      <section className="dashboard-hero">
        <div>
          <h2>{personalizedHeading}</h2>
          <p>Your dashboard uses completed interview results to highlight performance, consistency, and the best next practice.</p>
        </div>
        <button className="primary-btn hero-action" onClick={onStartInterview}>
          <StartIcon className="button-icon" size={18} strokeWidth={2} /> Start New Interview
        </button>
      </section>

      <div className="stat-grid dashboard-stat-grid">
        <StatBox
          icon={STAT_ICONS.totalInterviews}
          value={data.total_interviews}
          label="Completed Interviews"
        />
        <StatBox
          icon={STAT_ICONS.averageScore}
          value={metricValue(data.average_score)}
          label="Average Score"
          unit={data.average_score == null ? null : "/10"}
        />
        <StatBox
          icon={ACTION_ICONS.achievement}
          value={metricValue(data.highest_score ?? data.best_score)}
          label="Highest Score"
          unit={(data.highest_score ?? data.best_score) == null ? null : "/10"}
        />
        <StatBox
          icon={STAT_ICONS.correct}
          value={metricValue(data.recent_interview_score)}
          label="Recent Interview"
          unit={data.recent_interview_score == null ? null : "/10"}
        />
        <StatBox
          icon={STAT_ICONS.technicalRounds}
          value={metricValue(data.technical_performance)}
          label="Technical Performance"
          unit={data.technical_performance == null ? null : "/10"}
        />
        <StatBox
          icon={STAT_ICONS.hrRounds}
          value={metricValue(data.communication_performance)}
          label="Communication"
          unit={data.communication_performance == null ? null : "/10"}
        />
        <StatBox
          icon={STAT_ICONS.totalInterviews}
          value={data.weekly_practice_count}
          label="Last 7 Days"
          caption="Completed interviews"
        />
        <StatBox
          icon={STAT_ICONS.averageScore}
          value={improvement.label || "Not enough data yet"}
          label="Score Improvement"
          caption={
            improvement.status === "available"
              ? `Recent ${improvement.recent_count} vs. earlier interviews`
              : "Complete at least two scored interviews"
          }
        />
        <StatBox
          icon={STAT_ICONS.totalInterviews}
          value={data.interviews_this_month}
          label="This Month"
          caption="Completed interviews started this month"
        />
      </div>

      <div className="dashboard-content-grid">
        <SectionCard
          className="dashboard-section skill-performance-card"
          title="Skill Performance"
          subtitle="Your last several completed interviews, scored from 0 to 10."
        >
          <SkillPerformanceChart points={trend} />
        </SectionCard>

        <SectionCard
          className="dashboard-section recommendation-section"
          title="Recommended Next Interview"
          subtitle="A fast, rule-based suggestion from your weakest measured area."
        >
          {recommendation ? (
            <div className="recommendation-card">
              <span className="recommendation-kicker">Practice next</span>
              <strong>
                {recommendation.subject
                  ? `${formatLabel(recommendation.subject)} Technical`
                  : `${formatLabel(recommendation.round_type)} Round`}
              </strong>
              <p>{recommendation.reason}</p>
              <button className="primary-btn compact-btn" onClick={onStartInterview}>
                Start Recommended Practice
              </button>
            </div>
          ) : (
            <p className="subtle">Complete your first interview to receive a recommendation.</p>
          )}
        </SectionCard>
      </div>

      <SectionCard
        className="dashboard-section recent-history-section"
        title="Recent Interview History"
        subtitle="Your five most recently completed sessions."
      >
        <div className="dashboard-history-list">
          {recentInterviews.map((interview) => (
            <article key={interview.id} className="dashboard-history-row">
              <div>
                <strong>
                  {interview.round_type === "hr" ? "HR Interview" : formatLabel(interview.subject)}
                </strong>
                <span>{formatLabel(interview.round_type)} · {formatLabel(interview.difficulty)}</span>
              </div>
              <span className="dashboard-history-date">{interview.date}</span>
              <span className="dashboard-history-score">
                {interview.score == null ? "No score" : `${interview.score}/10`}
              </span>
              <button
                className="secondary-btn compact-btn"
                onClick={() => onViewInterview(interview.id)}
              >
                View Details
              </button>
            </article>
          ))}
        </div>
      </SectionCard>

      {(data.weak_subjects?.length || 0) > 0 && (
        <SectionCard className="dashboard-section focus-areas-section" title="Focus Areas" subtitle="Subjects currently averaging below 6/10.">
          <div className="pill-row">
            {data.weak_subjects.map((subject) => (
              <Pill key={subject} warn>{subject}</Pill>
            ))}
          </div>
        </SectionCard>
      )}
    </div>
  );
}
