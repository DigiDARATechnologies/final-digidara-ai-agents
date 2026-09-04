import { Mic, Send, Square, Volume2, X } from "lucide-react";

function getRepeatLabel(mode, item) {
  const itemMode = item?.practice_mode || item?.item_type || mode;
  if (itemMode === "minimal_pairs") return "Repeat both words";
  if (itemMode === "word") return "Repeat this word";
  if (itemMode === "daily" || itemMode === "daily_challenge") return "Repeat this challenge";
  return "Repeat this sentence";
}

function statusMessage(phase) {
  const copy = {
    loading_item: "Preparing your pronunciation item...",
    ready: "Listen to the reference, then record your voice.",
    playing_reference: "Reference voice is playing...",
    waiting_to_try: "Ready when you are.",
    listening: "Listening now...",
    transcript_ready: "Review your transcript before scoring.",
    submitting: "Submitting transcript and scoring pronunciation...",
    error: "Something needs attention.",
  };
  return copy[phase] || copy.ready;
}

export default function PronunciationWorkflow({
  phase,
  item,
  mode,
  transcript = "",
  error = "",
  onListen,
  onSpeak,
  onReview,
  onSubmit,
  onStartListening,
  onStopListening,
  onTranscriptChange,
  onCancel,
  minimalPairStep = 0,
  minimalPairResponses = [],
}) {
  const handleSpeak = onSpeak || onStartListening;
  const handleReview = onReview || onStopListening;
  const canRecord = phase === "ready" || phase === "waiting_to_try" || phase === "transcript_ready";
  const canSubmit = phase === "transcript_ready" && transcript.trim();
  const pair = item?.content?.pair || item?.metadata?.pair || [];
  const wordA = item?.content?.word_a || item?.metadata?.word_a || pair[0];
  const wordB = item?.content?.word_b || item?.metadata?.word_b || pair[1];
  const pairWords = [wordA, wordB].filter(Boolean);
  const isMinimalPairs = mode === "minimal_pairs" || item?.practice_mode === "minimal_pairs";
  const targetText = isMinimalPairs
    ? pairWords[minimalPairStep] || item?.text || "Your pronunciation item is loading."
    : item?.text || item?.content?.practice_text || "Your pronunciation item is loading.";

  return (
    <div className="space-y-5">
      <section className="rounded-3xl border border-slate-200 bg-white p-4 text-center shadow-sm sm:p-6">
        <p className="text-xs font-bold uppercase tracking-wide text-brand-600">
          {getRepeatLabel(mode, item)}
        </p>
        <h2 className="mx-auto mt-3 max-w-3xl break-words text-2xl font-bold leading-snug tracking-normal text-slate-900 md:text-3xl lg:text-4xl">
          {targetText}
        </h2>
        {isMinimalPairs && pairWords.length === 2 ? (
          <div className="mt-6 grid gap-3 md:grid-cols-2">
            {pairWords.map((word, index) => (
              <div
                key={word}
                className={`rounded-2xl border p-4 ${
                  index === minimalPairStep ? "border-brand-200 bg-brand-50" : "border-slate-200 bg-slate-50"
                }`}
              >
                <p className="text-xs font-bold uppercase text-slate-500">
                  {index === 0 ? "Word A" : "Word B"} {index < minimalPairResponses.length ? "- recorded" : ""}
                </p>
                <p className="mt-1 text-2xl font-bold text-slate-900">{word}</p>
                <button
                  type="button"
                  onClick={() => onListen?.(word)}
                  disabled={!onListen || phase === "loading_item" || phase === "submitting"}
                  className="mt-3 inline-flex min-h-11 items-center gap-2 rounded-full border border-brand-200 bg-white px-4 py-2 text-sm font-bold text-brand-700 transition hover:bg-brand-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Volume2 className="h-4 w-4" />
                  Play reference
                </button>
              </div>
            ))}
          </div>
        ) : (
          <button
            type="button"
            onClick={onListen}
            disabled={!onListen || phase === "loading_item" || phase === "submitting"}
            className="mt-6 inline-flex min-h-11 items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-5 py-2.5 text-sm font-bold text-brand-700 transition hover:bg-brand-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Volume2 className="h-4 w-4" />
            Play reference
          </button>
        )}
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
        {error && (
          <div id="pronunciation-error-banner" className="mb-4 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700">
            {error}
          </div>
        )}

        <div className="flex flex-col items-center gap-5 text-center">
          <div className="flex min-h-[96px] w-full max-w-xl items-center justify-center rounded-3xl bg-slate-50 px-4 py-6 sm:px-5">
            {phase === "listening" ? <Waveform /> : <StatusPanel phase={phase} />}
          </div>

          {(phase === "listening" || phase === "transcript_ready") && (
            <TranscriptPanel
              phase={phase}
              transcript={transcript}
              onTranscriptChange={onTranscriptChange}
            />
          )}

          {phase === "submitting" && (
            <div className="flex items-center justify-center gap-3 text-sm font-bold text-brand-700">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-600 border-t-transparent" />
              {statusMessage(phase)}
            </div>
          )}

          <div className="flex flex-col items-center gap-3">
            {phase === "listening" ? (
              <button
                type="button"
                onClick={handleReview}
                className="flex h-20 w-20 items-center justify-center rounded-full border border-red-200 bg-red-50 text-red-600 shadow-lg shadow-red-100 transition hover:bg-red-100"
                aria-label="Stop recording"
              >
                <Square className="h-8 w-8 fill-current" />
              </button>
            ) : canSubmit ? (
              <button
                type="button"
                onClick={onSubmit}
                className="flex h-20 w-20 items-center justify-center rounded-full bg-brand-600 text-white shadow-lg shadow-brand-600/25 transition hover:bg-brand-700"
                aria-label="Submit pronunciation"
              >
                <Send className="h-8 w-8" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSpeak}
                disabled={!canRecord || !handleSpeak}
                className="flex h-20 w-20 items-center justify-center rounded-full bg-brand-600 text-white shadow-lg shadow-brand-600/25 transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none"
                aria-label="Start recording"
              >
                <Mic className="h-9 w-9" />
              </button>
            )}
            <p className="text-xs font-semibold text-slate-500">
              {phase === "listening" ? "Tap to stop" : canSubmit ? (isMinimalPairs && minimalPairStep === 0 ? "Save word A" : "Tap to score") : statusMessage(phase)}
            </p>
          </div>

          {phase === "transcript_ready" && (
            <div className="flex flex-wrap justify-center gap-3">
              {handleSpeak && (
                <button
                  type="button"
                  onClick={handleSpeak}
                  className="min-h-11 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-600 transition hover:bg-slate-50"
                >
                  Record again
                </button>
              )}
              {onCancel && (
                <button
                  type="button"
                  onClick={onCancel}
                  className="inline-flex min-h-11 items-center gap-1 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-500 transition hover:bg-slate-50"
                >
                  <X className="h-4 w-4" />
                  Clear
                </button>
              )}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function StatusPanel({ phase }) {
  return (
    <div className="text-center">
      <div className="mx-auto mb-3 h-3 w-3 rounded-full bg-brand-500 shadow-[0_0_0_8px_rgba(37,99,235,0.10)]" />
      <p className="text-sm font-bold text-slate-800">{statusMessage(phase)}</p>
    </div>
  );
}

function Waveform() {
  return (
    <div className="flex h-16 items-center justify-center gap-1.5" aria-hidden="true">
      {Array.from({ length: 21 }).map((_, index) => (
        <span
          key={index}
          className="w-1.5 rounded-full bg-brand-500"
          style={{
            height: `${18 + ((index * 17) % 42)}px`,
            animation: "pronunciation-wave 900ms ease-in-out infinite",
            animationDelay: `${index * 45}ms`,
          }}
        />
      ))}
    </div>
  );
}

function TranscriptPanel({ phase, transcript, onTranscriptChange }) {
  const label = phase === "listening" ? "Live transcript" : "Final transcript";
  if (phase === "transcript_ready") {
    return (
      <label className="w-full max-w-2xl text-left">
        <span className="text-xs font-bold uppercase tracking-wide text-slate-500">{label}</span>
        <textarea
          value={transcript}
          onChange={(event) => onTranscriptChange?.(event.target.value)}
          placeholder="No transcript detected. Speak again or edit text here..."
          rows={3}
          className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm font-medium leading-6 text-slate-800 outline-none transition focus:border-brand-500 focus:bg-white focus:ring-2 focus:ring-brand-100"
        />
      </label>
    );
  }
  return (
    <div className="w-full max-w-2xl rounded-2xl border border-slate-200 bg-slate-50 p-4 text-left">
      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-2 min-h-6 text-sm font-medium leading-6 text-slate-800">
        {transcript || "Speak clearly into your microphone..."}
      </p>
    </div>
  );
}
