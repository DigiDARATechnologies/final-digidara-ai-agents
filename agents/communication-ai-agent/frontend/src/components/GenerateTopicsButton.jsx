import { RefreshCw } from "lucide-react";

export default function GenerateTopicsButton({ loading, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      aria-disabled={loading}
      aria-busy={loading}
      className="inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-xl border border-indigo-600 bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-indigo-700 active:bg-indigo-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-indigo-600"
    >
      <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
      {loading ? "Generating Topics..." : "Generate More Topics"}
    </button>
  );
}
