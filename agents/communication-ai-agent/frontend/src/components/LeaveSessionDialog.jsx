import { useEffect, useRef } from "react";

export default function LeaveSessionDialog({
  open,
  title = "Leave this session?",
  message = "Your current answer or session progress may not be saved.",
  stayLabel = "Stay and Continue",
  leaveLabel = "Leave Session",
  onStay,
  onLeave,
}) {
  const stayButtonRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const previousActive = document.activeElement;
    const focusTimer = window.setTimeout(() => stayButtonRef.current?.focus(), 0);
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onStay?.();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.clearTimeout(focusTimer);
      window.removeEventListener("keydown", handleKeyDown);
      previousActive?.focus?.();
    };
  }, [open, onStay]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/45 px-4 backdrop-blur-sm" role="presentation">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="leave-session-title"
        aria-describedby="leave-session-message"
        className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-5 shadow-2xl shadow-slate-900/20"
      >
        <h2 id="leave-session-title" className="text-lg font-bold text-slate-900">{title}</h2>
        <p id="leave-session-message" className="mt-2 text-sm leading-6 text-slate-600">{message}</p>
        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            ref={stayButtonRef}
            type="button"
            onClick={onStay}
            className="min-h-11 rounded-xl border border-brand-100 bg-brand-50 px-4 py-2 text-sm font-bold text-brand-700 transition hover:bg-brand-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-300"
          >
            {stayLabel}
          </button>
          <button
            type="button"
            onClick={onLeave}
            className="min-h-11 rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm font-bold text-red-600 transition hover:bg-red-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-200"
          >
            {leaveLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
