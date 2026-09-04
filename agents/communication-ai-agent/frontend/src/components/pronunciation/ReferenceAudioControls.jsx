export default function ReferenceAudioControls({
  muted,
  locale,
  voices,
  voiceName,
  playing,
  disabled = false,
  daily = false,
  onLocaleChange,
  onListen,
  onSlowListen,
  onListenLine,
  onReplayLine,
  onStop,
  onMuteToggle,
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4" aria-labelledby="audio-controls-title">
      <h2 id="audio-controls-title" className="text-sm font-bold text-slate-900">
        Reference Audio
      </h2>
      <p className="mt-1 text-xs text-slate-500">
        Selected reference accent: {locale} | Voice: {voiceName || "Browser default"}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button onClick={onListen} disabled={disabled} className="rounded-xl bg-brand-600 px-4 py-2 text-sm font-bold text-white disabled:opacity-50">
          {daily ? "Listen All" : playing ? "Replay" : "Listen"}
        </button>
        <button onClick={onSlowListen} disabled={disabled} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-600 disabled:opacity-50">
          {daily ? "Listen All Slowly" : "Listen Slowly"}
        </button>
        {daily && (
          <>
            <button onClick={onListenLine} disabled={disabled} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-600 disabled:opacity-50">
              Listen Line by Line
            </button>
            <button onClick={onReplayLine} disabled={disabled} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-600 disabled:opacity-50">
              Replay Current Line
            </button>
          </>
        )}
        <button onClick={onStop} disabled={disabled && !playing} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-600 disabled:opacity-50">
          Stop Audio
        </button>
        <button onClick={onMuteToggle} disabled={disabled} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-600 disabled:opacity-50">
          {muted ? "Unmute" : "Mute"}
        </button>
      </div>
      <label className="mt-3 block text-xs font-bold text-slate-500" htmlFor="reference-accent">
        Reference accent
      </label>
      <select
        id="reference-accent"
        value={locale}
        onChange={(event) => onLocaleChange(event.target.value)}
        disabled={disabled}
        className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
      >
        {["en-US", "en-GB", "en-IN"].map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
      <p className="mt-2 text-xs text-slate-400" aria-live="polite">
        {playing ? "Reference voice is playing. Microphone recording is paused." : `Available English voices: ${voices.length || "browser default"}`}
      </p>
    </section>
  );
}
