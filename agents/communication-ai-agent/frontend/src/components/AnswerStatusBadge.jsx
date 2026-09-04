const STATUS_STYLES = {
  Correct: "border-emerald-200 bg-emerald-50 text-emerald-700",
  "Mostly Correct": "border-lime-200 bg-lime-50 text-lime-700",
  "Partially Correct": "border-amber-200 bg-amber-50 text-amber-700",
  "Needs Improvement": "border-red-200 bg-red-50 text-red-700",
  "Off Topic": "border-red-200 bg-red-50 text-red-700",
  "No Answer": "border-slate-200 bg-slate-50 text-slate-600",
};

export default function AnswerStatusBadge({ status }) {
  const label = status || "Review Unavailable";
  const style = STATUS_STYLES[label] || "border-slate-200 bg-slate-50 text-slate-600";

  return (
    <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-bold ${style}`} aria-label={`Answer status: ${label}`}>
      {label}
    </span>
  );
}
