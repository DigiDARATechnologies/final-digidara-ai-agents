import { ArrowLeft } from "lucide-react";

export default function ModuleBackButton({ label = "Back", onBack, disabled = false, className = "" }) {
  return (
    <button
      type="button"
      onClick={onBack}
      disabled={disabled}
      aria-label={label}
      className={`inline-flex min-h-11 items-center gap-2 rounded-full border border-brand-100 bg-white/90 px-4 py-2 text-sm font-bold text-brand-700 shadow-sm transition hover:border-brand-200 hover:bg-brand-50 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
    >
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      <span className="hidden sm:inline">{label}</span>
      <span className="sm:hidden">Back</span>
    </button>
  );
}
