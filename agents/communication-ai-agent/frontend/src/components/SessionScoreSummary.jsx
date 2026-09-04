import ScoreRing from "./ScoreRing.jsx";

function sessionScores(session) {
  const type = session?.type;
  const mode = session?.mode;
  if (type === "writing") {
    return [
      ["Grammar", session.grammar_score ?? session.scores?.grammar],
      ["Vocabulary", session.vocabulary_score ?? session.scores?.vocabulary],
      ["Clarity", session.clarity_score ?? session.scores?.clarity],
      ...(mode === "topic" ? [["Knowledge", session.knowledge_score ?? session.scores?.knowledge]] : []),
    ];
  }
  return [
    ["Confidence", session?.confidence_score ?? session?.scores?.confidence],
    ["Fluency", session?.fluency_score ?? session?.scores?.fluency],
    ["Grammar", session?.grammar_score ?? session?.scores?.grammar],
    ...(mode === "topic"
      ? [["Knowledge", session?.knowledge_score ?? session?.scores?.knowledge]]
      : [["Clarity", session?.clarity_score ?? session?.scores?.clarity]]),
  ];
}

export default function SessionScoreSummary({ session }) {
  const scores = sessionScores(session);

  return (
    <section aria-labelledby="session-scores" className="rounded-2xl border border-slate-200 bg-white p-5">
      <h2 id="session-scores" className="sr-only">
        Session scores
      </h2>
      <div className="flex justify-center">
        <ScoreRing score={session?.overall_score ?? session?.scores?.overall} label="Overall Score" size={110} />
      </div>
      <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {scores.map(([label, value]) => (
          <ScoreRing key={label} score={value} label={label} size={72} stroke={6} />
        ))}
      </div>
    </section>
  );
}
