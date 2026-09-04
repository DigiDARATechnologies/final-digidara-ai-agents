import { X } from "lucide-react";

export default function DailyChallengeReminder({ status, moduleLabel, onStart, onDismiss, loading = false }) {
  if (!status || status.completed || status.completed_today) return null;

  const xpReward = Number(status.xp_reward ?? 0);
  const title = status.title || `Daily ${moduleLabel} Challenge`;
  const statusText = String(status.status || "not_started").replace(/_/g, " ");

  return (
    <section className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-900 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-amber-700">Daily challenge reminder</p>
          <h2 className="mt-1 text-base font-extrabold text-slate-900">
            You haven&apos;t done today&apos;s {title} yet.
          </h2>
          <p className="mt-1 text-sm text-amber-800">
            {xpReward} XP waiting — keep your streak alive. Current status:{" "}
            <span className="font-bold capitalize">{statusText}</span>.
          </p>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss daily challenge reminder"
          className="rounded-full p-1 text-amber-700 transition hover:bg-amber-100"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      <button
        type="button"
        onClick={onStart}
        disabled={loading}
        className="mt-4 inline-flex min-h-10 items-center rounded-xl bg-brand-600 px-4 py-2 text-sm font-bold text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? "Starting..." : "Start Daily Challenge"}
      </button>
    </section>
  );
}
