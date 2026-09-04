import ScoreRing from "../ScoreRing.jsx";
import { formatScore10 } from "../../utils/scoreFormat.js";

export default function PronunciationScoreCard({ result }) {
  const scores = result?.scores || {};
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5" aria-labelledby="pronunciation-score-title">
      <h2 id="pronunciation-score-title" className="text-base font-bold text-slate-900">
        Pronunciation Result
      </h2>
      <div className="mt-4 grid gap-4 md:grid-cols-[160px_1fr]">
        <div className="flex flex-col items-center justify-center rounded-xl bg-slate-50 p-4">
          <ScoreRing score={scores.overall} label="Overall" size={104} />
          <p className="mt-2 text-sm font-bold text-slate-800">Speech Match: {result?.match_percentage ?? 0}%</p>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Score label="Word Accuracy" value={scores.word_accuracy} />
          <Score label="Completeness" value={scores.completeness} />
          <Score label="Clarity" value={scores.clarity} />
          <Score label="Fluency" value={scores.fluency} />
        </div>
      </div>
      {result?.validation_message && (
        <p className="mt-4 rounded-xl bg-slate-50 p-3 text-xs font-bold text-slate-700">
          {result.validation_message}
        </p>
      )}
      <p className="mt-4 rounded-xl bg-amber-50 p-3 text-xs text-amber-800">
        This score is based on recognised words, sentence accuracy and speaking clarity. It is not a certified phonetic assessment.
      </p>
    </section>
  );
}

function Score({ label, value }) {
  return (
    <div className="rounded-xl bg-slate-50 p-3">
      <p className="text-xs font-bold text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-bold text-slate-900">{formatScore10(value)}</p>
    </div>
  );
}
