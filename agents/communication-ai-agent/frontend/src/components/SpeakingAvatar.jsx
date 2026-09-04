export default function SpeakingAvatar({ talking = false, state = "ready" }) {
  const status = talking ? "Speaking" : state === "listening" ? "Listening" : "Ready";

  return (
    <section className="mx-auto mb-4 flex w-full max-w-sm flex-col items-center" aria-label={`AI coach avatar ${status}`}>
      <div className={`relative h-28 w-28 ${talking ? "animate-speaking-bob" : "animate-idle-bob"}`}>
        <div className="absolute inset-0 rounded-full bg-brand-100 shadow-lg shadow-brand-100/50" />
        <svg viewBox="0 0 160 160" className="relative h-full w-full" role="img" aria-hidden="true">
          <defs>
            <linearGradient id="coachFace" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#eff6ff" />
              <stop offset="100%" stopColor="#dbeafe" />
            </linearGradient>
          </defs>
          <circle cx="80" cy="80" r="62" fill="url(#coachFace)" stroke="#3154d4" strokeWidth="5" />
          <path d="M44 66c8-16 23-23 36-23s28 7 36 23" fill="none" stroke="#1e293b" strokeWidth="6" strokeLinecap="round" opacity="0.18" />
          <circle cx="58" cy="76" r="8" fill="#0f172a" className={talking ? "" : "animate-avatar-blink"} />
          <circle cx="102" cy="76" r="8" fill="#0f172a" className={talking ? "" : "animate-avatar-blink"} />
          <circle cx="55" cy="73" r="2.5" fill="#ffffff" />
          <circle cx="99" cy="73" r="2.5" fill="#ffffff" />
          <path d="M73 85c2.5 3 6.5 3 9 0" fill="none" stroke="#64748b" strokeWidth="4" strokeLinecap="round" />
          {talking ? (
            <ellipse cx="80" cy="108" rx="17" ry="10" fill="#1e293b" className="animate-avatar-mouth" />
          ) : (
            <path d="M64 106c9 9 23 9 32 0" fill="none" stroke="#1e293b" strokeWidth="6" strokeLinecap="round" />
          )}
          <path d="M34 108c-9-11-13-26-9-40 3-16 14-30 29-38" fill="none" stroke="#3154d4" strokeWidth="8" strokeLinecap="round" opacity="0.35" />
          <path d="M126 108c9-11 13-26 9-40-3-16-14-30-29-38" fill="none" stroke="#3154d4" strokeWidth="8" strokeLinecap="round" opacity="0.35" />
        </svg>
        <span className={`absolute bottom-2 right-2 h-5 w-5 rounded-full border-2 border-white ${talking ? "bg-emerald-500" : "bg-slate-300"}`} />
      </div>
      <p className="mt-2 rounded-full bg-white px-3 py-1 text-xs font-bold text-slate-600 shadow-sm">
        AI Coach - {status}
      </p>
    </section>
  );
}
