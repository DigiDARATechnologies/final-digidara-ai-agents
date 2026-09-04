import { useEffect, useState } from "react";

/**
 * AIAvatarFace — presentational SVG avatar that animates its mouth while speaking.
 *
 * Props:
 *   speaking  {boolean}  – drives the open/closed mouth toggle animation
 *   name      {string}   – label shown beneath the avatar
 *   status    {string}   – small status line ("Speaking…" / "Listening to you" / etc.)
 */
export default function AIAvatarFace({ speaking = false, name = "AI Coach", status = "" }) {
  const [mouthOpen, setMouthOpen] = useState(false);

  /* Toggle mouth every ~180 ms while speaking; reset when silent. */
  useEffect(() => {
    if (!speaking) {
      setMouthOpen(false);
      return;
    }
    const interval = setInterval(() => {
      setMouthOpen((prev) => !prev);
    }, 180);
    return () => clearInterval(interval);
  }, [speaking]);

  /* ── Mouth paths ────────────────────────────────────────────────────────── */


  return (
    <div className="flex flex-col items-center">
      {/* Circle with optional speaking glow ring */}
      <div
        className={[
          "relative flex items-center justify-center rounded-full bg-gradient-to-br from-brand-50 to-sky-50",
          "border-2 transition-all duration-300 w-40 h-40 sm:w-48 sm:h-48",
          speaking
            ? "border-teal-400 shadow-[0_0_0_4px_rgba(45,212,191,0.25),0_0_32px_8px_rgba(45,212,191,0.2)]"
            : "border-brand-100 shadow-lg",
        ].join(" ")}
      >
        {/* Subtle pulse overlay when speaking */}
        {speaking && (
          <span
            style={{
              position: "absolute",
              inset: 0,
              borderRadius: "50%",
              backgroundColor: "#2dd4bf",
              opacity: 0.1,
              animation: "ping 1.2s cubic-bezier(0,0,0.2,1) infinite",
              pointerEvents: "none",
            }}
          />
        )}

        <svg
          viewBox="0 0 200 200"
          className="h-full w-full select-none"
          aria-label={speaking ? `${name} is speaking` : name}
        >
          {/* Head */}
          <circle cx="100" cy="105" r="70" fill="#F5E6D8" />
          {/* Hair */}
          <path d="M35 90 Q40 30 100 30 Q160 30 165 90 Q165 60 100 55 Q35 60 35 90 Z" fill="#4f46e5" />
          {/* Ears */}
          <circle cx="32" cy="108" r="10" fill="#F5E6D8" />
          <circle cx="168" cy="108" r="10" fill="#F5E6D8" />
          {/* Eyes */}
          <ellipse cx="75" cy="100" rx="7" ry="9" fill="#2A2A3C" />
          <ellipse cx="125" cy="100" rx="7" ry="9" fill="#2A2A3C" />
          {/* Eyebrows */}
          <path d="M62 82 Q75 76 88 83" stroke="#5C4632" strokeWidth="3" fill="none" strokeLinecap="round" />
          <path d="M112 83 Q125 76 138 82" stroke="#5C4632" strokeWidth="3" fill="none" strokeLinecap="round" />
          {/* Cheeks */}
          <ellipse cx="68" cy="122" rx="10" ry="6" fill="#F0B8A8" opacity="0.5" />
          <ellipse cx="132" cy="122" rx="10" ry="6" fill="#F0B8A8" opacity="0.5" />
          {/* Collar / professional touch */}
          <path d="M70 168 L100 150 L130 168 L130 190 L70 190 Z" fill="#4338ca" />
          {/* Mouth: two states toggled by `mouthOpen` */}
          {mouthOpen ? (
            <ellipse cx="100" cy="135" rx="16" ry="12" fill="#8B4A3D" /> // open/talking
          ) : (
            <path d="M82 132 Q100 144 118 132" stroke="#8B4A3D" strokeWidth="4" fill="none" strokeLinecap="round" /> // closed/smile
          )}
        </svg>
      </div>

      {/* Label */}
      <p className="mt-3 text-sm font-bold text-slate-900">{name}</p>
      {status && (
        <p
          className={[
            "mt-0.5 text-xs font-semibold",
            speaking ? "text-teal-600" : "text-slate-500",
          ].join(" ")}
        >
          {status}
        </p>
      )}
    </div>
  );
}
