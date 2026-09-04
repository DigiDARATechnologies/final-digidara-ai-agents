const COPY = {
  loading_item: {
    title: "Preparing your practice",
    body: "I am choosing a pronunciation item for your level.",
  },
  ready: {
    title: "Listen first",
    body: "Play the reference voice once. Then repeat it clearly when you are ready.",
  },
  playing_reference: {
    title: "Reference voice is speaking",
    body: "Listen carefully. The microphone is off so it will not hear the reference audio.",
  },
  waiting_to_try: {
    title: "Your turn",
    body: "Now repeat the reference. Speak naturally, then stop when you are done.",
  },
  listening: {
    title: "I am listening",
    body: "Repeat the word or sentence clearly. Click I'm Done Speaking when finished.",
  },
  transcript_ready: {
    title: "Review your transcript",
    body: "Edit the recognised words if needed. Nothing is submitted until you click Submit Pronunciation.",
  },
  submitting: {
    title: "Checking your speech match",
    body: "I am comparing the reference with the recognised words and preparing feedback.",
  },
  showing_result: {
    title: "Nice work",
    body: "Review your score, practise the highlighted words, then retry if you want to improve.",
  },
  error: {
    title: "Something needs attention",
    body: "Use the message below to recover and continue practice.",
  },
};

export default function PronunciationCoachPanel({ phase, attempt, maxAttempts = 3, error }) {
  const copy = COPY[phase] || COPY.ready;
  return (
    <section className="rounded-2xl border border-brand-100 bg-brand-50 p-5" aria-live="polite">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-bold uppercase text-brand-600">Friendly Voice Coach</p>
          <h2 className="mt-1 text-lg font-bold text-slate-900">{copy.title}</h2>
          <p className="mt-1 text-sm text-slate-600">{error || copy.body}</p>
        </div>
        <div className="rounded-xl bg-white px-4 py-3 text-sm font-bold text-brand-700">
          Attempt {attempt?.attempt_number || 1} of {attempt?.max_attempts || maxAttempts}
        </div>
      </div>
    </section>
  );
}
