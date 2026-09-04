/**
 * IconButton — a circular icon button with a small label underneath.
 * Used in the Speaking page bottom action bar.
 *
 * Props:
 *   icon     {ReactNode}  – icon element to render inside the circle
 *   label    {string}     – short text label shown beneath the circle
 *   onClick  {function}   – click handler
 *   tone     {"default"|"danger"|"primary"}  – color variant
 *   disabled {boolean}   – disables the button
 */
export default function IconButton({ icon, label, onClick, tone = "default", disabled = false }) {
  const circleClass =
    tone === "danger"
      ? "bg-red-50 text-red-600 shadow-red-100"
      : tone === "primary"
      ? "bg-brand-600 text-white shadow-brand-600/25"
      : "border border-slate-200 bg-white text-slate-600 shadow-slate-200/70";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex flex-col items-center gap-1.5 text-xs font-semibold text-slate-500 transition-transform duration-150 hover:scale-105 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
    >
      <span
        className={`flex h-14 w-14 items-center justify-center rounded-full shadow-lg backdrop-blur-sm transition-colors duration-200 ${circleClass}`}
      >
        {icon}
      </span>
      <span className="select-none">{label}</span>
    </button>
  );
}
