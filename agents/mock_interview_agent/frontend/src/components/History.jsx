import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getHistory, getHistoryDetail } from "../api";
import EmptyState from "./ui/EmptyState";
import PageHeader from "./ui/PageHeader";
import ScoreBar from "./ui/ScoreBar";
import SectionCard from "./ui/SectionCard";
import QuestionScorecard from "./QuestionScorecard";
import { SkeletonStack } from "./ui/Skeleton";
import StatBox from "./ui/StatBox";
import { APP_ICONS } from "../utils/icons";
import { AI_ASSESSMENT_CAPTION, HR_ASSESSMENT_CAPTION } from "../utils/verdict";
import { reportClientError } from "../utils/clientLogger";

const BackIcon = APP_ICONS.back;
const HISTORY_PAGE_SIZE = 10;

function formatLabel(value) {
  if (!value) return "—";
  return String(value)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatInterviewDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

function scoreTone(value) {
  if (value === null || value === undefined) return "score-empty";
  const score = Number(value);
  if (score >= 8) return "score-high";
  if (score >= 5) return "score-mid";
  return "score-low";
}

/**
 * List and detail view for previous interview attempts.
 * @param {{ studentId: number }} props
 */
export default function History({ studentId }) {
  const navigate = useNavigate();
  const { interviewId: routeInterviewId } = useParams();
  const interviewId = routeInterviewId ? Number(routeInterviewId) : null;
  const [list, setList] = useState([]);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(null);
  const [pagination, setPagination] = useState({
    page: 1,
    limit: HISTORY_PAGE_SIZE,
    total_items: 0,
    total_pages: 0,
    has_more: false,
  });

  useEffect(() => {
    if (interviewId) return undefined;
    let isMounted = true;

    async function loadHistory() {
      await Promise.resolve();
      if (!isMounted) return;
      setLoading(true);
      setError(null);
      try {
        const response = await getHistory(studentId, 1, HISTORY_PAGE_SIZE);
        if (!isMounted) return;
        setList(response.items);
        setPagination(response.pagination);
      } catch (requestError) {
        reportClientError("history_load_failed", requestError, {
          student_id: studentId,
        });
        if (isMounted) {
          setError(
            requestError.message
            || "Unable to load interview history. Please try again."
          );
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadHistory();

    return () => {
      isMounted = false;
    };
  }, [studentId, interviewId]);

  async function loadMore() {
    if (loadingMore || !pagination.has_more) return;
    setLoadingMore(true);
    setError(null);
    const nextPage = pagination.page + 1;
    try {
      const response = await getHistory(
        studentId,
        nextPage,
        HISTORY_PAGE_SIZE
      );
      setList((current) => [...current, ...response.items]);
      setPagination(response.pagination);
    } catch (error) {
      reportClientError("history_page_load_failed", error, {
        student_id: studentId,
        page: nextPage,
      });
      setError(error.message || "Unable to load more interviews. Please try again.");
    } finally {
      setLoadingMore(false);
    }
  }

  const openDetail = useCallback((id) => {
    navigate(`/history/${id}`);
  }, [navigate]);

  useEffect(() => {
    if (!interviewId) return undefined;
    let isMounted = true;

    async function loadDetail() {
      await Promise.resolve();
      if (!isMounted) return;
      setDetailLoading(true);
      setDetail(null);
      setError(null);
      try {
        const response = await getHistoryDetail(interviewId);
        if (isMounted) setDetail(response);
      } catch (requestError) {
        reportClientError("history_detail_load_failed", requestError, {
          interview_id: interviewId,
        });
        if (isMounted) {
          setError(
            requestError.message
            || "Unable to load that interview. Please try again."
          );
        }
      } finally {
        if (isMounted) setDetailLoading(false);
      }
    }

    loadDetail();
    return () => {
      isMounted = false;
    };
  }, [interviewId]);

  if (interviewId && detailLoading) {
    return (
      <div className="page history-detail-page">
        <SkeletonStack rows={4} />
      </div>
    );
  }

  if (interviewId && error && !detail) {
    return (
      <div className="page history-detail-page">
        <button className="secondary-btn back-btn" onClick={() => navigate("/history")}>
          <BackIcon size={17} strokeWidth={2} aria-hidden="true" />
          Back to History
        </button>
        <p className="error-text" role="alert">{error}</p>
      </div>
    );
  }

  if (interviewId && detail) {
    const interview = detail.interview;
    const assessmentCaption = interview.round_type === "hr"
      ? HR_ASSESSMENT_CAPTION
      : AI_ASSESSMENT_CAPTION;
    const hasResult = interview.overall_score !== null
      && interview.overall_score !== undefined;

    return (
      <div className="page history-detail-page">
        <button className="secondary-btn back-btn" onClick={() => navigate("/history")}>
          <BackIcon size={17} strokeWidth={2} aria-hidden="true" />
          Back to History
        </button>
        <PageHeader
          eyebrow="Interview transcript"
          title={`${interview.round_type === "hr" ? "HR" : interview.subject} Interview`}
          description={`${formatLabel(interview.status)} ${interview.difficulty} session with its available question and answer transcript.`}
        />

        <div className="stat-grid history-summary-grid">
          <StatBox value={interview.round_type === "hr" ? "HR" : interview.subject} label="Interview" />
          <StatBox value={interview.difficulty} label="Difficulty" />
          <StatBox
            value={hasResult ? interview.overall_score : "—"}
            label="AI Assessment Score"
            unit={hasResult ? "/10" : null}
            caption={assessmentCaption}
          />
          <StatBox
            value={detail.focus_loss_count || 0}
            label="Focus Losses"
            caption={`${detail.focus_loss_total_seconds || 0}s away`}
          />
        </div>

        {detail.integrity_flagged && (
          <div className="integrity-detail-notice">
            <span className="integrity-flag-badge">Integrity Flagged</span>
            <p>
              This label records repeated or extended focus loss; it does not
              change the interview score.
            </p>
          </div>
        )}

        <QuestionScorecard
          scorecard={detail.scorecard}
          totalMarks={detail.total_marks}
          maxMarks={detail.max_marks}
        />

        {hasResult && (
          <SectionCard
            title="AI Assessment Score"
            subtitle={assessmentCaption}
          >
            <ScoreBar label="AI Assessment Score" value={interview.overall_score} />
          </SectionCard>
        )}
      </div>
    );
  }

  return (
    <div className="page history-page">
      <PageHeader
        eyebrow="Records"
        title="Interview History"
        description="Browse completed interviews and review their results and transcripts."
      />

      <SectionCard className="history-list-card">
        <div className="history-toolbar">
          <div>
            <strong>{pagination.total_items}</strong>
            <span>completed interviews</span>
          </div>
          {detailLoading && <span className="subtle">Opening interview...</span>}
        </div>

        {loading && <SkeletonStack rows={4} />}
        {error && <p className="error-text" role="alert">{error}</p>}
        {!loading && !error && list.length === 0 && (
          <EmptyState
            title="No past interviews yet"
            message="Your completed interviews will appear here with scores and answer transcripts."
          />
        )}

        {list.length > 0 && (
          <div className="history-table-scroll">
            <div className="history-table" role="table" aria-label="Interview history">
              <div className="history-table-head" role="row">
                <span>Student ID</span>
                <span>Student Name</span>
                <span>Interview</span>
                <span>Round</span>
                <span>Job Role</span>
                <span>Difficulty</span>
                <span>Interview Date</span>
                <span>Score</span>
                <span>Action</span>
              </div>
              {list.map((item) => (
                <div key={item.id} className="history-table-row" role="row">
                  <div data-label="Student ID">{item.student_id ?? "—"}</div>
                  <div data-label="Student Name">
                    <strong>{item.student_name || "—"}</strong>
                  </div>
                  <div data-label="Interview">
                    <strong>{item.role_name || (item.round_type === "hr" ? "HR Interview" : item.subject || "Technical Interview")}</strong>
                    <span className="subtle">Practice session</span>
                    {item.integrity_flagged && (
                      <span className="integrity-flag-badge compact">
                        Integrity Flagged
                      </span>
                    )}
                  </div>
                  <div data-label="Round">
                    <span className={`history-pill round-${item.round_type === "hr" ? "hr" : "technical"}`}>
                      {item.round_type === "hr" ? "HR" : "Technical"}
                    </span>
                  </div>
                  <div data-label="Job Role">{item.role_name || item.job_role || "Not set"}</div>
                  <div data-label="Difficulty">
                    <span className={`history-pill difficulty-${String(item.difficulty || "").toLowerCase()}`}>
                      {formatLabel(item.difficulty)}
                    </span>
                  </div>
                  <div data-label="Interview Date">{formatInterviewDate(item.started_at)}</div>
                  <div data-label="Score" className={`history-score ${scoreTone(item.overall_score)}`}>
                    {item.overall_score === null || item.overall_score === undefined
                      ? "—"
                      : `${item.overall_score}/10`}
                  </div>
                  <div data-label="Action">
                    <button className="primary-btn compact-btn history-view-btn" onClick={() => openDetail(item.id)}>
                      {item.status === "completed" ? "View Result" : "View Details"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
            {pagination.has_more && (
              <button
                type="button"
                className="secondary-btn history-load-more"
                onClick={loadMore}
                disabled={loadingMore}
              >
                {loadingMore ? "Loading more…" : "Load more interviews"}
              </button>
            )}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
