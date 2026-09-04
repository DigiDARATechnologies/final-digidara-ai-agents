import ScoreRing from "../ScoreRing.jsx";

export default function WritingFeedback({ feedback, mode, onEdit, onRewrite, onNext, isComplete }) {
  const scores = feedback?.scores || feedback || {};
  const entries = [
    ["Grammar", scores.grammar ?? feedback?.grammar],
    ["Vocabulary", scores.vocabulary ?? feedback?.vocabulary],
    ["Clarity", scores.clarity ?? feedback?.clarity],
    ["Spelling", scores.spelling ?? feedback?.spelling],
    [mode === "topic" ? "Knowledge" : "Relevance", mode === "topic" ? scores.knowledge ?? feedback?.knowledge : scores.relevance ?? feedback?.relevance],
    ["Overall", scores.overall ?? feedback?.overall],
  ].filter(([, value]) => value != null);

  return (
    <section className="mt-6 space-y-4">
      <div className="rounded-xl border border-emerald-100 bg-emerald-50 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase text-emerald-700">AI Teacher Feedback</p>
            <h2 className="mt-1 text-lg font-bold text-slate-900">{feedback?.status || "Reviewed"}</h2>
          </div>
          <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-emerald-700">
            {feedback?.appreciation || "Good attempt."}
          </span>
        </div>
        <p className="mt-3 text-sm text-slate-700">{feedback?.short_feedback || feedback?.feedback}</p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        {entries.map(([label, value]) => (
          <ScoreRing key={label} score={value} label={label} size={64} stroke={5} />
        ))}
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <FeedbackBlock title="Your Answer">{feedback?.original_answer}</FeedbackBlock>
        <CopyBlock title="Corrected Version" text={feedback?.corrected_answer} />
        <CopyBlock title="Better Natural Version" text={feedback?.better_natural_answer} />
        <FeedbackBlock title="Explanation" listItems={feedback?.mistake_points || []}>{feedback?.explanation}</FeedbackBlock>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <ListBlock title="Strengths" items={feedback?.strengths} />
        <ListBlock title="Areas To Improve" items={feedback?.areas_to_improve} />
      </div>

      <Corrections items={feedback?.mistakes} />
      <Vocabulary items={feedback?.vocabulary_suggestions} />

      <div className="flex flex-col gap-2 md:flex-row">
        <button type="button" onClick={onEdit} className="rounded-xl border border-slate-200 px-4 py-3 text-sm font-bold text-slate-600 transition hover:bg-slate-50">
          Edit and Retry
        </button>
        <button type="button" onClick={onRewrite} className="rounded-xl border border-brand-200 px-4 py-3 text-sm font-bold text-brand-700 transition hover:bg-brand-50">
          Rewrite Using Suggestions
        </button>
        <button type="button" onClick={onNext} className="flex-1 rounded-xl bg-brand-600 px-4 py-3 text-sm font-bold text-white transition hover:bg-brand-700">
          {isComplete ? "View Session Result" : "Continue to Next Prompt"}
        </button>
      </div>
    </section>
  );
}

function FeedbackBlock({ title, children, listItems = [] }) {
  const hasList = title === "Explanation" && listItems.length > 0;
  return (
    <div className="rounded-xl bg-slate-50 p-4">
      <p className="text-xs font-bold uppercase text-slate-500">{title}</p>
      {hasList ? (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
          {listItems.map((item, index) => (
            <li key={`${title}-${index}`}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{children || "Not available."}</p>
      )}
    </div>
  );
}

function CopyBlock({ title, text }) {
  const copyText = async () => {
    if (!text || !navigator.clipboard) return;
    await navigator.clipboard.writeText(text);
  };
  return (
    <div className="rounded-xl bg-slate-50 p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-bold uppercase text-slate-500">{title}</p>
        <button type="button" onClick={copyText} className="rounded-lg border border-slate-200 px-2 py-1 text-xs font-bold text-slate-600">
          Copy
        </button>
      </div>
      <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{text || "Not available."}</p>
    </div>
  );
}

function ListBlock({ title, items = [] }) {
  return (
    <div className="rounded-xl bg-slate-50 p-4">
      <p className="text-xs font-bold uppercase text-slate-500">{title}</p>
      <ul className="mt-2 space-y-1 text-sm text-slate-700">
        {(items.length ? items : ["Not available for this attempt."]).map((item, index) => (
          <li key={`${item}-${index}`}>- {item}</li>
        ))}
      </ul>
    </div>
  );
}

function Corrections({ items = [] }) {
  if (!items.length) return null;
  return (
    <div className="rounded-xl bg-slate-50 p-4">
      <p className="text-xs font-bold uppercase text-slate-500">Corrections</p>
      <div className="mt-3 space-y-2">
        {items.map((item, index) => (
          <div key={`${item.incorrect}-${index}`} className="rounded-lg bg-white p-3 text-sm text-slate-700">
            <p className="font-semibold">{item.type || "Issue"}</p>
            <p className="mt-1">{item.incorrect || "Original"} {"->"} {item.correct || "Correction"}</p>
            {Array.isArray(item.mistake_points) && item.mistake_points.length > 0 ? (
              <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-500">
                {item.mistake_points.map((point, pointIndex) => (
                  <li key={`${item.incorrect}-${pointIndex}`}>{point}</li>
                ))}
              </ul>
            ) : item.explanation ? (
              <p className="mt-1 text-slate-500">{item.explanation}</p>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function Vocabulary({ items = [] }) {
  if (!items.length) return null;
  return (
    <div className="rounded-xl bg-slate-50 p-4">
      <p className="text-xs font-bold uppercase text-slate-500">Vocabulary Suggestions</p>
      <div className="mt-3 space-y-2">
        {items.map((item, index) => (
          <div key={`${item.suggestion}-${index}`} className="rounded-lg bg-white p-3 text-sm text-slate-700">
            <p className="font-semibold">{item.original || "Phrase"} {"->"} {item.suggestion || "Suggestion"}</p>
            {item.example && <p className="mt-1 text-slate-500">{item.example}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
