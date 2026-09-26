import { useState } from "react";
import { Link } from "react-router-dom";
import client from "../api/client.js";
import QuestionReviewList from "./QuestionReviewList.jsx";
import RecommendationCard from "./RecommendationCard.jsx";
import SessionScoreSummary from "./SessionScoreSummary.jsx";
import StrengthsCard from "./StrengthsCard.jsx";
import WeaknessesCard from "./WeaknessesCard.jsx";

function normalizeSession(session, summary) {
  const source = { ...(session || {}), ...(summary || {}) };
  return {
    ...source,
    topic_title: source.topic_title || source.daily_category || "Practice Session",
    summary_feedback: source.summary_feedback || source.summary,
    strengths: source.strengths || [],
    areas_to_improve: source.areas_to_improve || [],
    turns: source.turns || session?.turns || [],
  };
}

export default function SessionResultDashboard({ session, summary, type, onStartAnother, startAnotherLabel = "Start Another Session", onRetry, showActions = true, embedded = false }) {
  const data = normalizeSession({ ...session, type: type || session?.type }, summary);
  const modeLabel = data.mode === "topic" ? "Topic-wise" : type === "writing" ? "Daily Writing Challenge" : "Daily Speaking Challenge";
  const dateLabel = data.created_at ? new Date(data.created_at).toLocaleDateString() : new Date().toLocaleDateString();

  const [downloading, setDownloading] = useState(false);

  async function handleDownloadPdf() {
    if (!data?.id) return;
    setDownloading(true);
    try {
      const isWriting = Boolean(type === "writing" || data?.type === "writing" || data?.mode === "topic" && data?.turns?.[0]?.user_response !== undefined);
      const endpoint = isWriting
        ? `/writing/report/${data.id}/pdf`
        : `/speaking/report/${data.id}/pdf`;
      const response = await client.get(endpoint, {
        responseType: "blob",
      });
      const blob = new Blob([response.data], { type: "application/pdf" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      const prefix = isWriting ? "Writing" : "Speaking";
      link.download = `${prefix}_Report_${data.id}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("PDF download failed", err);
      alert("Could not download report PDF: " + (err.response?.data?.message || err.message));
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className={embedded ? "space-y-5" : "mx-auto max-w-4xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8"}>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Session Result</h1>
        <p className="mt-1 text-sm text-slate-500">
          {data.topic_title} - {modeLabel} {type === "writing" ? "Writing" : "Speaking"}{data.mode === "topic" ? ` - ${data.difficulty}` : ""} - {dateLabel}
        </p>
      </header>

      <div className="mt-6 space-y-5">
        <SessionScoreSummary session={data} />

        <section className="rounded-2xl border border-slate-200 bg-white p-4" aria-labelledby="summary-title">
          <h2 id="summary-title" className="text-sm font-bold text-slate-900">
            Session Summary
          </h2>
          <p className="mt-2 text-sm text-slate-600">
            {data.summary_feedback || "Detailed summary is unavailable for this session."}
          </p>
        </section>

        <div className="grid gap-4 md:grid-cols-2">
          <StrengthsCard items={data.strengths} />
          <WeaknessesCard items={data.areas_to_improve} />
        </div>

        <QuestionReviewList turns={data.turns} type={type || data.type} onRetry={onRetry} />

        <RecommendationCard recommendation={data.recommendation} nextPractice={data.next_practice_suggestion} />

        {showActions && <div className="flex flex-wrap gap-2">
          {data?.id && (
            <button
              onClick={handleDownloadPdf}
              disabled={downloading}
              className="min-h-10 rounded-xl bg-emerald-600 hover:bg-emerald-700 px-4 py-2 text-sm font-bold text-white flex items-center gap-1.5 transition-colors disabled:opacity-50"
            >
              📄 {downloading ? "Downloading PDF..." : "Download PDF Report"}
            </button>
          )}
          {onStartAnother && (
            <button onClick={onStartAnother} className="min-h-10 rounded-xl bg-brand-600 px-4 py-2 text-sm font-bold text-white">
              {startAnotherLabel}
            </button>
          )}
          <Link to="/history" className="min-h-10 rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-600">
            Go to History
          </Link>
          <Link to="/dashboard" className="min-h-10 rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-600">
            Back to Dashboard
          </Link>
        </div>}
      </div>
    </div>
  );
}
