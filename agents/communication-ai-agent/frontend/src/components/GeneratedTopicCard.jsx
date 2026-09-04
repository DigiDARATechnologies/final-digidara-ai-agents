import { RefreshCw, Sparkles } from "lucide-react";

function formatDuration(seconds) {
  if (!seconds) return null;
  if (seconds <= 60) return "30 to 60 seconds";
  if (seconds <= 120) return "1 to 2 minutes";
  return "2 to 3 minutes";
}

export default function GeneratedTopicCard({ topic, loading, error, onRegenerate, regenerateLabel = "Generate Another Topic" }) {
  return (
    <div className="mt-5 rounded-3xl border border-slate-200 bg-white p-4 shadow-soft sm:p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          <div className="mb-3 flex items-center gap-3">
            <span className="learning-card-icon"><Sparkles className="h-5 w-5" /></span>
            <p className="text-xs font-bold uppercase tracking-wide text-brand-600">
            {topic?.mode === "daily_conversation" ? "Generated Situation" : "AI Generated Topic"}
            </p>
          </div>
          {loading ? (
            <p className="text-sm font-medium text-slate-500">Generating a new topic...</p>
          ) : topic ? (
            <>
              <h2 className="text-lg font-bold text-slate-900">{topic.title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">{topic.description}</p>
            </>
          ) : (
            <p className="text-sm font-medium text-slate-500">No topic generated yet.</p>
          )}
        </div>
        <button
          type="button"
          onClick={onRegenerate}
          disabled={loading}
          className="inline-flex min-h-11 w-full shrink-0 items-center justify-center gap-2 rounded-2xl border border-brand-200 bg-brand-50 px-4 py-2 text-xs font-bold text-brand-700 transition hover:border-brand-300 hover:bg-brand-100 disabled:opacity-50 sm:w-auto"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          {regenerateLabel}
        </button>
      </div>

      {topic && !loading && (
        <div className="mt-4 flex flex-wrap gap-2 text-xs font-semibold text-slate-500">
          <span className="learning-badge capitalize">{topic.difficulty}</span>
          {topic.expected_duration_seconds && (
            <span className="learning-badge">Expected speaking time: {formatDuration(topic.expected_duration_seconds)}</span>
          )}
          {topic.minimum_word_count && topic.maximum_word_count && (
            <span className="learning-badge">
              Expected words: {topic.minimum_word_count} to {topic.maximum_word_count}
            </span>
          )}
          {topic.source === "fallback" && <span className="rounded-full bg-amber-50 px-3 py-1 text-amber-700">Fallback topic</span>}
        </div>
      )}

      {error && !loading && (
        <p className="mt-3 rounded-lg border border-amber-100 bg-amber-50 p-3 text-sm font-medium text-amber-700">
          {error}
        </p>
      )}
    </div>
  );
}
