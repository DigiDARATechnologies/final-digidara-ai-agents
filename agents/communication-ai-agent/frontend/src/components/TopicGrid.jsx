export default function TopicGrid({ topics, selected, onSelect }) {
  if (!topics.length) {
    return <p className="text-sm text-slate-400">No topics found for this difficulty yet.</p>;
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {topics.map((topic) => (
        <button
          key={topic.id}
          onClick={() => onSelect(topic)}
          className={`learning-card text-left ${
            selected?.id === topic.id
              ? "border-brand-500 bg-brand-50"
              : ""
          }`}
        >
          <div>
            <span className="learning-card-icon">{String(topic.title || "?").slice(0, 1).toUpperCase()}</span>
            <p className="mt-4 text-sm font-bold text-slate-800">{topic.title}</p>
            <p className="mt-2 text-xs leading-5 text-slate-500">{topic.description}</p>
          </div>
          <span className="learning-badge mt-4">{selected?.id === topic.id ? "Selected" : "Practice topic"}</span>
        </button>
      ))}
    </div>
  );
}
