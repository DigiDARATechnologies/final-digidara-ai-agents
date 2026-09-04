export default function WritingGoalCard({ goal, totalPrompts }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase text-brand-600">Writing Goal</p>
          <h2 className="mt-1 text-base font-bold text-slate-900">{goal.topic}</h2>
        </div>
        <div className="flex flex-wrap gap-2 text-xs font-bold text-slate-600">
          <span className="rounded-full bg-slate-100 px-3 py-1">Prompt {goal.promptNumber} / {totalPrompts}</span>
          <span className="rounded-full bg-slate-100 px-3 py-1 capitalize">{goal.difficulty}</span>
        </div>
      </div>

      <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
        <GoalItem label="Word Goal" value={goal.expectedWordCount} />
        <GoalItem label="Suggested Time" value={goal.suggestedTime} />
        <GoalItem label="Target Tone" value={goal.targetTone} />
      </div>

      <div className="mt-4 rounded-lg bg-brand-50 p-3">
        <p className="text-xs font-bold uppercase text-brand-600">Skill Focus</p>
        <p className="mt-1 text-sm text-slate-700">{goal.skillFocus}</p>
      </div>

      <div className="mt-4">
        <p className="text-xs font-bold uppercase text-slate-500">Required Points</p>
        <ul className="mt-2 space-y-1 text-sm text-slate-600">
          {goal.requiredPoints.map((point) => (
            <li key={point}>- {point}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function GoalItem({ label, value }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <p className="text-xs font-bold uppercase text-slate-500">{label}</p>
      <p className="mt-1 font-semibold text-slate-800">{value}</p>
    </div>
  );
}
