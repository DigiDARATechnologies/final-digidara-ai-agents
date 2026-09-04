import { Link } from "react-router-dom";
import ScoreRing from "./ScoreRing.jsx";

export default function dailySessionSummary({ summary, onStartAnother }) {
  const scores = [
    ["Confidence", summary?.confidence_score],
    ["Fluency", summary?.fluency_score],
    ["Grammar", summary?.grammar_score],
    ["Clarity", summary?.clarity_score],
  ];
  return (
    <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <header><p className="text-xs font-bold uppercase tracking-[0.18em] text-brand-600">Daily Speaking Challenge Complete</p><h1 className="mt-2 text-2xl font-extrabold text-slate-900">20 / 20 Questions</h1><p className="mt-1 text-sm text-slate-500">A quick look at your everyday speaking progress.</p></header>
      <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-5 shadow-soft sm:p-7">
        <div className="flex justify-center"><ScoreRing score={summary?.overall_score} label="Overall" size={112} /></div>
        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">{scores.map(([label, value]) => <ScoreRing key={label} score={value} label={label} size={72} stroke={6} />)}</div>
      </section>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="text-sm font-bold text-slate-900">Your Strengths</h2><p className="mt-2 text-sm leading-6 text-slate-600">{summary?.summary_feedback || "You kept the conversation moving."}</p><ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-600">{(summary?.strengths || []).slice(0, 4).map((item) => <li key={item}>{item}</li>)}</ul></section>
        <section className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="text-sm font-bold text-slate-900">Today's Vocabulary</h2><div className="mt-3 flex flex-wrap gap-2">{(summary?.daily_vocabulary || []).map((word) => <span key={word} className={`rounded-full px-3 py-1 text-xs font-bold ${summary?.daily_vocab_used?.includes(word) ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>{summary?.daily_vocab_used?.includes(word) ? "✓ " : "○ "}{word}</span>)}</div><p className="mt-3 text-xs font-semibold text-slate-500">Vocabulary used: {summary?.daily_vocab_used?.length || 0} / 3</p></section>
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        {[['Best Answer', summary?.best_answer], ['Needs More Practice', summary?.needs_practice]].map(([title, item]) => item && <section key={title} className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="text-sm font-bold text-slate-900">{title}</h2><p className="mt-3 text-xs font-bold uppercase tracking-wide text-slate-400">AI asked</p><p className="mt-1 text-sm text-slate-700">{item.question}</p><p className="mt-3 text-xs font-bold uppercase tracking-wide text-slate-400">Your answer</p><p className="mt-1 text-sm text-slate-700">{item.answer}</p>{item.corrected_answer && <p className="mt-3 text-sm font-semibold text-emerald-700">Correction: {item.corrected_answer}</p>}</section>)}
      </div>
      <section className="mt-5 rounded-2xl border border-brand-100 bg-brand-50 p-5"><h2 className="text-sm font-bold text-slate-900">Tomorrow's Focus</h2><p className="mt-2 text-sm leading-6 text-slate-700">{summary?.recommendation || "Keep answering in complete, natural sentences."}</p>{summary?.next_practice_suggestion && <p className="mt-2 text-xs font-semibold text-brand-700">{summary.next_practice_suggestion}</p>}</section>
      <div className="mt-6 flex flex-wrap gap-2"><button type="button" onClick={onStartAnother} className="min-h-10 rounded-xl bg-brand-600 px-4 py-2 text-sm font-bold text-white">Continue practising</button><Link to="/history" className="min-h-10 rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-600">View History</Link></div>
    </div>
  );
}
