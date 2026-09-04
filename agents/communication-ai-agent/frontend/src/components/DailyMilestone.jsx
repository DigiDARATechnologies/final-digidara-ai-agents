export default function DailyMilestone({ answered }) {
  const messages = {
    5: "You're giving clearer answers. Keep going!",
    10: "Halfway there — your conversation is flowing well.",
    15: "Five more to go. Keep speaking naturally!",
  };
  if (!messages[answered]) return null;
  return <p className="mb-3 rounded-xl border border-brand-100 bg-brand-50 px-4 py-2 text-center text-xs font-bold text-brand-700">{answered} / 20 Complete · {messages[answered]}</p>;
}
