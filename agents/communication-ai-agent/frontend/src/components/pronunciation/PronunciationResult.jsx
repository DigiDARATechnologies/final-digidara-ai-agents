import { ArrowRight, CheckCircle2, Lightbulb, RotateCcw, Target, Volume2 } from "lucide-react";
import { formatScoreNumber } from "../../utils/scoreFormat.js";

function toScore(value) {
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return null;
  return Math.max(0, Math.min(numeric > 10 ? numeric / 10 : numeric, 10));
}

function getScore(result, keys) {
  const scores = result?.scores || {};
  for (const key of keys) {
    const value = scores[key] ?? result?.[key];
    const score = toScore(value);
    if (score != null) return score;
  }
  return null;
}

function overallScore(result) {
  return getScore(result, ["overall", "overall_score"]) ?? toScore(result?.match_percentage);
}

function scoreTone(score) {
  if (score == null) return "text-slate-500";
  if (score >= 8) return "text-emerald-700";
  if (score >= 5.5) return "text-amber-700";
  return "text-red-700";
}

function resultTone(score) {
  if (score == null) return "border-slate-200 bg-slate-50";
  if (score >= 8) return "border-emerald-200 bg-emerald-50";
  if (score >= 5.5) return "border-amber-200 bg-amber-50";
  return "border-red-200 bg-red-50";
}

function wordTone(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "correct") return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (normalized === "extra" || normalized === "extra repetition" || normalized === "missing" || normalized === "needs practice") {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }
  if (normalized === "different" || normalized === "incorrect") return "border-red-200 bg-red-50 text-red-700";
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function statusLabel(status) {
  const value = String(status || "Needs review").replace(/_/g, " ").trim();
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function normalizeResult(result) {
  const comparison = result?.comparison || {};
  const feedback = result?.feedback || {};
  const wordResults = result?.word_results || comparison.word_results || [];
  const minimalPairResults = result?.minimal_pair_results || comparison.minimal_pair_results || [];
  const distinguishability = result?.distinguishability || comparison.distinguishability;
  const correctWords = result?.correct_words || comparison.correct_words || [];
  const missingWords = result?.missing_words || comparison.missing_words || [];
  const differentWords = result?.different_words || comparison.different_words || [];
  const extraWords = result?.extra_words || comparison.extra_words || [];
  const wordsToPractice = Array.isArray(feedback.words_to_practice) ? feedback.words_to_practice : [];
  const phoneticFeedback = Array.isArray(feedback.phonetic_feedback) ? feedback.phonetic_feedback : [];

  return {
    feedback,
    wordResults,
    minimalPairResults,
    distinguishability,
    correctWords,
    missingWords,
    differentWords,
    extraWords,
    wordsToPractice,
    phoneticFeedback,
    targetText: result?.expected_text || result?.reference_text || comparison.expected_text || "Reference text unavailable.",
    detectedText: result?.recognised_text || comparison.recognised_text || "No recognised speech was returned.",
    validationMessage: result?.validation_message || comparison.validation_message,
  };
}

function issuesFromResult(data) {
  const issues = [];
  data.missingWords.forEach((word) => issues.push({ label: word, status: "Missing", detail: "This target word was not recognised." }));
  data.extraWords.forEach((word) => issues.push({ label: word, status: "Extra", detail: "This word was heard but was not part of the target." }));
  data.differentWords.forEach((item) => {
    if (typeof item === "string") {
      issues.push({ label: item, status: "Different", detail: "This word was recognised differently from the target." });
    } else {
      issues.push({
        label: item.expected || "Target word",
        status: "Different",
        detail: item.recognised ? `Heard as "${item.recognised}".` : "This word was recognised differently from the target.",
      });
    }
  });
  data.wordResults
    .filter((word) => String(word.status || "").toLowerCase() !== "correct")
    .forEach((word) => {
      const label = word.word || word.expected || word.recognised || "Word";
      if (!issues.some((issue) => issue.label === label && issue.status === statusLabel(word.status))) {
        issues.push({
          label,
          status: statusLabel(word.status),
          detail: word.recognised && word.recognised !== label ? `Heard as "${word.recognised}".` : "Needs another clear repetition.",
        });
      }
    });
  return issues;
}

export default function PronunciationResult({ result, onListenAgain, onTryAgain, onNext }) {
  if (!result) return null;
  const data = normalizeResult(result);
  const overall = overallScore(result);
  const scorePercent = Math.round((overall ?? 0) * 10);
  const correctCount = data.wordResults.filter((word) => String(word.status || "").toLowerCase() === "correct").length || data.correctWords.length;
  const issues = issuesFromResult(data);
  const hasIssues = issues.length > 0 || data.wordsToPractice.length > 0;
  const primaryFeedback = data.feedback.feedback || data.validationMessage || "Your recognised speech was compared with the reference text.";
  const appreciation = data.feedback.appreciation || (overall != null && overall >= 8 ? "Strong attempt." : "Good practice attempt.");
  const practiceTip = data.feedback.practice_tip || data.feedback.next_instruction;

  return (
    <section className="space-y-5" aria-labelledby="pronunciation-result-title">
      <div className={`overflow-hidden rounded-3xl border shadow-sm ${resultTone(overall)}`}>
        <div className="grid gap-0 lg:grid-cols-[280px_1fr]">
          <div className="flex flex-col items-center justify-center border-b border-white/70 bg-white/70 p-6 text-center lg:border-b-0 lg:border-r">
            <div
              className="grid h-36 w-36 place-items-center rounded-full"
              style={{ background: `conic-gradient(#4f46e5 ${scorePercent * 3.6}deg, #e2e8f0 0deg)` }}
            >
              <div className="grid h-28 w-28 place-items-center rounded-full bg-white shadow-sm">
                <div>
                  <p className={`text-4xl font-bold tracking-normal ${scoreTone(overall)}`}>{formatScoreNumber(overall, "0.0")}</p>
                  <p className="text-xs font-bold uppercase text-slate-400">out of 10</p>
                </div>
              </div>
            </div>
            <h2 id="pronunciation-result-title" className="mt-4 text-xl font-bold text-slate-900">
              Pronunciation Result
            </h2>
            <p className="mt-1 text-sm font-semibold text-slate-600">Speech match: {result.match_percentage ?? scorePercent}%</p>
          </div>

          <div className="space-y-5 bg-white p-5 sm:p-6">
            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-brand-600">AI pronunciation coach</p>
              <p className="mt-2 text-xl font-bold text-slate-900">{appreciation}</p>
              <p className="mt-2 text-sm leading-6 text-slate-600">{primaryFeedback}</p>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <MetricCard label="Accuracy" value={getScore(result, ["accuracy", "word_accuracy"])} />
              <MetricCard label="Clarity" value={getScore(result, ["clarity"])} />
              <MetricCard label="Fluency" value={getScore(result, ["fluency"])} />
              <MetricCard label="Completeness" value={getScore(result, ["completeness"])} />
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.15fr_0.85fr]">
        <div className="space-y-5">
          <DashboardCard title="Target vs detected speech" icon={<Target className="h-4 w-4" />}>
            <div className="grid gap-3 md:grid-cols-2">
              <TextPanel label="Target" text={data.targetText} tone="target" />
              <TextPanel label="Detected" text={data.detectedText} tone="detected" />
            </div>
          </DashboardCard>

          {data.minimalPairResults.length > 0 && (
            <DashboardCard title="Minimal pair contrast" icon={<Volume2 className="h-4 w-4" />}>
              <div className="grid gap-3 md:grid-cols-2">
                {data.minimalPairResults.map((pair) => (
                  <div key={pair.word} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs font-bold uppercase text-slate-500">Target word</p>
                        <p className="mt-1 text-2xl font-bold text-slate-900">{pair.word}</p>
                      </div>
                      <p className="rounded-full bg-white px-3 py-1 text-sm font-bold text-brand-700">
                        {formatScoreNumber(pair.scores?.overall ?? pair.match_percentage, "0.0")} / 10
                      </p>
                    </div>
                    <p className="mt-3 text-sm text-slate-600">Detected: {pair.recognised_text || "None"}</p>
                    {pair.validation_message && <p className="mt-2 text-xs font-medium text-slate-500">{pair.validation_message}</p>}
                  </div>
                ))}
              </div>
              {data.distinguishability && (
                <div className={`mt-3 rounded-2xl border p-4 ${data.distinguishability.passed ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}>
                  <p className={`text-sm font-bold ${data.distinguishability.passed ? "text-emerald-800" : "text-amber-800"}`}>
                    {data.distinguishability.passed ? "The words sounded distinguishable." : "The words need more contrast."}
                  </p>
                  <p className="mt-1 text-sm text-slate-700">{data.distinguishability.message}</p>
                </div>
              )}
            </DashboardCard>
          )}

          {data.wordResults.length > 0 && (
            <DashboardCard title="Word-by-word analysis" icon={<CheckCircle2 className="h-4 w-4" />}>
              <div className="flex flex-wrap gap-2">
                {data.wordResults.map((word, index) => (
                  <span
                    key={`${word.word}-${word.recognised}-${index}`}
                    className={`rounded-2xl border px-3 py-2 text-sm font-bold ${wordTone(word.status)}`}
                    title={word.recognised && word.recognised !== word.word ? `Heard: ${word.recognised}` : word.status}
                  >
                    {word.word || word.recognised || "Word"} <span className="font-medium opacity-80">- {statusLabel(word.status)}</span>
                  </span>
                ))}
              </div>
            </DashboardCard>
          )}
        </div>

        <div className="space-y-5">
          <DashboardCard title="What was correct" icon={<CheckCircle2 className="h-4 w-4" />}>
            {correctCount > 0 ? (
              <div className="flex flex-wrap gap-2">
                {(data.correctWords.length ? data.correctWords : data.wordResults.filter((word) => String(word.status || "").toLowerCase() === "correct").map((word) => word.word)).map((word, index) => (
                  <span key={`${word}-${index}`} className="rounded-full bg-emerald-50 px-3 py-1 text-sm font-bold text-emerald-700">
                    {word}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-sm leading-6 text-slate-600">No fully correct target words were returned for this attempt.</p>
            )}
          </DashboardCard>

          <DashboardCard title="What needs work" icon={<Target className="h-4 w-4" />}>
            {hasIssues ? (
              <div className="space-y-2">
                {issues.map((issue, index) => (
                  <div key={`${issue.label}-${index}`} className={`rounded-2xl border p-3 text-sm ${wordTone(issue.status)}`}>
                    <p className="font-bold">{issue.label} - {issue.status}</p>
                    <p className="mt-1 text-slate-700">{issue.detail}</p>
                  </div>
                ))}
                {data.wordsToPractice.map((item, index) => (
                  <div key={`${item.word || item}-${index}`} className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm">
                    <p className="font-bold text-amber-800">{item.word || item}</p>
                    {item.reason && <p className="mt-1 text-slate-700">{item.reason}</p>}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm leading-6 text-slate-600">No specific problem words were returned. Keep repeating the full item to build consistency.</p>
            )}
          </DashboardCard>

          <DashboardCard title="Why it happened" icon={<Lightbulb className="h-4 w-4" />}>
            <div className="space-y-2 text-sm leading-6 text-slate-700">
              {data.validationMessage && <p>{data.validationMessage}</p>}
              {data.distinguishability?.message && <p>{data.distinguishability.message}</p>}
              <p>{primaryFeedback}</p>
            </div>
          </DashboardCard>

          <DashboardCard title="How to pronounce it correctly" icon={<Volume2 className="h-4 w-4" />}>
            <div className="space-y-3">
              {data.phoneticFeedback.length > 0 && data.phoneticFeedback.map((hint, index) => (
                <div key={`${hint.word}-${index}`} className="rounded-2xl border border-brand-100 bg-brand-50 p-3 text-sm">
                  <p className="font-bold text-brand-800">
                    {hint.word}{hint.ipa ? ` - ${hint.ipa}` : ""}
                  </p>
                  <p className="mt-1 text-slate-700">{hint.tip || hint.reason || "Repeat this word slowly, then say it naturally."}</p>
                </div>
              ))}
              {practiceTip && <p className="rounded-2xl border border-amber-100 bg-amber-50 p-3 text-sm leading-6 text-slate-700">{practiceTip}</p>}
              {data.feedback.next_instruction && <p className="text-sm leading-6 text-slate-600">{data.feedback.next_instruction}</p>}
            </div>
          </DashboardCard>
        </div>
      </div>

      <div className="flex flex-col gap-3 rounded-3xl border border-slate-200 bg-white p-4 shadow-sm md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm font-bold text-slate-900">Practise again</p>
          <p className="text-sm text-slate-500">Review the reference, repeat slowly, then try the item again.</p>
        </div>
        <div className="flex w-full flex-wrap gap-2 md:w-auto">
          {onListenAgain && (
            <ActionButton onClick={onListenAgain} icon={<Volume2 className="h-4 w-4" />}>
              Review Reference
            </ActionButton>
          )}
          <ActionButton onClick={onTryAgain} icon={<RotateCcw className="h-4 w-4" />}>
            Try Again
          </ActionButton>
          <ActionButton primary onClick={onNext} icon={<ArrowRight className="h-4 w-4" />}>
            Next Question
          </ActionButton>
        </div>
      </div>
    </section>
  );
}

function MetricCard({ label, value }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-xs font-bold uppercase text-slate-500">{label}</p>
      <p className={`mt-2 text-2xl font-bold ${scoreTone(value)}`}>{formatScoreNumber(value, "-")}</p>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white">
        <div className="h-full rounded-full bg-brand-500" style={{ width: `${Math.max(0, Math.min((value ?? 0) * 10, 100))}%` }} />
      </div>
    </div>
  );
}

function DashboardCard({ title, icon, children }) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      <div className="mb-3 flex items-center gap-2">
        <span className="grid h-8 w-8 place-items-center rounded-xl bg-brand-50 text-brand-700">{icon}</span>
        <h3 className="text-sm font-bold uppercase tracking-wide text-slate-600">{title}</h3>
      </div>
      {children}
    </section>
  );
}

function TextPanel({ label, text, tone }) {
  const classes = tone === "target" ? "border-brand-100 bg-brand-50" : "border-slate-200 bg-slate-50";
  return (
    <div className={`rounded-2xl border p-4 ${classes}`}>
      <p className="text-xs font-bold uppercase text-slate-500">{label}</p>
      <p className="mt-2 whitespace-pre-wrap text-sm font-semibold leading-6 text-slate-800">{text}</p>
    </div>
  );
}

function ActionButton({ children, icon, onClick, primary = false }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-full px-4 py-2.5 text-sm font-bold transition md:flex-none ${
        primary
          ? "border border-brand-200 bg-brand-600 text-white hover:bg-brand-700"
          : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
      }`}
    >
      {icon}
      {children}
    </button>
  );
}
