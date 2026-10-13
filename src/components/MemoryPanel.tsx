import { useEffect, useState, type FormEvent } from "react";
import {
  addMemory,
  deleteMemory,
  fetchMemories,
  pinMemory,
  type LearnerMemory,
  type MemoryKind,
} from "../lib/learnerApi";

interface Props {
  agentLabels: Record<string, string>;
  onToast: (message: string) => void;
}

const SOURCE_LABELS: Record<string, string> = { user: "You", readiness: "Readiness check", coach: "Career coach" };
const ADD_KINDS: { id: MemoryKind; label: string }[] = [
  { id: "preference", label: "Preference" },
  { id: "goal", label: "Goal" },
  { id: "note", label: "Note" },
];

/** Everything the agents remember about the learner -- visible, and theirs to delete. */
export default function MemoryPanel({ agentLabels, onToast }: Props) {
  const [memories, setMemories] = useState<LearnerMemory[] | null>(null);
  const [text, setText] = useState("");
  const [kind, setKind] = useState<MemoryKind>("preference");
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    let active = true;
    fetchMemories().then((rows) => active && setMemories(rows)).catch(() => active && setMemories([]));
    return () => { active = false; };
  }, []);

  async function add(event: FormEvent) {
    event.preventDefault();
    if (text.trim().length < 2) return;
    try {
      const created = await addMemory(text.trim(), kind);
      setMemories((rows) => [created, ...(rows ?? []).filter((r) => r.id !== created.id)]);
      setText("");
      onToast("Saved. Every agent will remember this.");
    } catch (err) {
      onToast((err as Error).message);
    }
  }

  async function togglePin(memory: LearnerMemory) {
    try {
      const updated = await pinMemory(memory.id, !memory.pinned);
      setMemories((rows) => (rows ?? []).map((r) => (r.id === updated.id ? updated : r)));
    } catch (err) {
      onToast((err as Error).message);
    }
  }

  async function remove(memory: LearnerMemory) {
    try {
      await deleteMemory(memory.id);
      setMemories((rows) => (rows ?? []).filter((r) => r.id !== memory.id));
    } catch (err) {
      onToast((err as Error).message);
    }
  }

  const visible = showAll ? memories ?? [] : (memories ?? []).slice(0, 8);
  const sourceLabel = (m: LearnerMemory) => SOURCE_LABELS[m.source] ?? agentLabels[m.source] ?? m.source;

  return (
    <section className="pv-section rd-panel">
      <h2>What your agents remember</h2>
      <p className="rd-muted">Every agent uses these to personalise your practice. You can pin what matters most or delete anything.</p>
      <form className="mem-add" onSubmit={add}>
        <input value={text} maxLength={500} placeholder="e.g. Explain answers in Tamil, I'm targeting product companies"
          onChange={(e) => setText(e.target.value)} />
        <select value={kind} onChange={(e) => setKind(e.target.value as MemoryKind)} aria-label="Type">
          {ADD_KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}
        </select>
        <button className="btn btn-primary btn-sm" disabled={text.trim().length < 2}>Remember</button>
      </form>
      <div className="mem-list">
        {memories === null && <p className="rd-muted">Loading…</p>}
        {memories && memories.length === 0 && <p className="rd-muted">Nothing yet. Practise with any agent, or add something above.</p>}
        {visible.map((memory) => (
          <div key={memory.id} className="mem-row">
            <span className={`mem-kind kind-${memory.kind}`}>{memory.kind}</span>
            <p>{memory.text}</p>
            <small>{sourceLabel(memory)}</small>
            <button type="button" className={memory.pinned ? "pinned" : ""} aria-pressed={memory.pinned}
              title={memory.pinned ? "Unpin" : "Pin"} onClick={() => void togglePin(memory)}>★</button>
            <button type="button" title="Delete" aria-label={`Delete: ${memory.text}`} onClick={() => void remove(memory)}>✕</button>
          </div>
        ))}
      </div>
      {memories && memories.length > 8 && (
        <button type="button" className="link-btn" onClick={() => setShowAll(!showAll)}>
          {showAll ? "Show fewer" : `Show all ${memories.length}`}
        </button>
      )}
    </section>
  );
}
