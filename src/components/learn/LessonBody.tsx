import { useState } from "react";
import type { ReactNode } from "react";
import { findAgent } from "../../data/agents";
import { highlight } from "../../lib/learnHighlight";
import { parseBlocks, parseQa, renderInline, type Block } from "../../lib/learnMarkdown";

export interface LessonBodyProps {
  body: string;
  kind: string;
  /** Opens an agent from a "Practise this" box. Without it the box is text only. */
  onOpenAgent?: (agentId: string) => void;
}

const CALLOUTS: Record<string, { icon: string; label: string }> = {
  tip: { icon: "💡", label: "Tip" },
  note: { icon: "ℹ️", label: "Note" },
  warning: { icon: "⚠️", label: "Watch out" },
  remember: { icon: "📌", label: "Remember" },
  formula: { icon: "∑", label: "Formula" },
  example: { icon: "✏️", label: "Worked example" },
  trick: { icon: "⚡", label: "Shortcut" },
  interview: { icon: "🎤", label: "Interview tip" },
  practice: { icon: "▶", label: "Practise this" },
};

function CodeBox({ lang, code }: { lang: string; code: string }) {
  const [copied, setCopied] = useState(false);
  const isOutput = lang === "output";
  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard blocked: the text can still be selected by hand */ }
  }
  return (
    <figure className={`lh-code${isOutput ? " is-output" : ""}`}>
      <figcaption>
        <span>{isOutput ? "Output" : lang || "code"}</span>
        {!isOutput && <button type="button" onClick={() => void copy()} aria-label="Copy code">{copied ? "Copied" : "Copy"}</button>}
      </figcaption>
      <pre><code>{isOutput ? code : highlight(code, lang)}</code></pre>
    </figure>
  );
}

function Callout({ block, onOpenAgent }: { block: Extract<Block, { t: "callout" }>; onOpenAgent?: (id: string) => void }) {
  const known = CALLOUTS[block.kind];
  const meta = known ?? CALLOUTS.note;
  const agent = block.kind === "practice" ? findAgent(block.arg) : undefined;
  const title = block.kind === "example" && block.arg ? block.arg : meta.label;
  return (
    <aside className={`lh-callout kind-${known ? block.kind : "note"}`}>
      <header><span aria-hidden="true">{meta.icon}</span><b>{block.kind === "example" ? `${meta.label}: ${title}` : title}</b></header>
      <div className="lh-callout-body"><Blocks blocks={block.blocks} onOpenAgent={onOpenAgent} /></div>
      {agent && onOpenAgent && (
        <button type="button" className="lh-callout-action" onClick={() => onOpenAgent(agent.id)}>Open {agent.name} →</button>
      )}
    </aside>
  );
}

export function Blocks({ blocks, onOpenAgent }: { blocks: Block[]; onOpenAgent?: (id: string) => void }): ReactNode {
  return (
    <>
      {blocks.map((block, index) => {
        const key = `${block.t}-${index}`;
        switch (block.t) {
          case "h":
            return block.level === 2
              ? <h2 key={key} id={block.id}>{renderInline(block.text, key)}</h2>
              : <h3 key={key} id={block.id}>{renderInline(block.text, key)}</h3>;
          case "p":
            return <p key={key}>{renderInline(block.text, key)}</p>;
          case "list": {
            const Tag = block.ordered ? "ol" : "ul";
            return <Tag key={key}>{block.items.map((item, i) => <li key={i}>{renderInline(item, `${key}-${i}`)}</li>)}</Tag>;
          }
          case "code":
            return <CodeBox key={key} lang={block.lang} code={block.code} />;
          case "table":
            return (
              <div key={key} className="lh-table-wrap">
                <table>
                  <thead><tr>{block.head.map((cell, i) => <th key={i}>{renderInline(cell, `${key}h${i}`)}</th>)}</tr></thead>
                  <tbody>{block.rows.map((row, r) => (
                    <tr key={r}>{row.map((cell, c) => <td key={c}>{renderInline(cell, `${key}-${r}-${c}`)}</td>)}</tr>
                  ))}</tbody>
                </table>
              </div>
            );
          case "callout":
            return <Callout key={key} block={block} onOpenAgent={onOpenAgent} />;
          case "hr":
            return <hr key={key} />;
        }
      })}
    </>
  );
}

const LEVEL_LABEL: Record<string, string> = { easy: "Easy", medium: "Medium", hard: "Hard" };

/** Interview questions: each one a card that opens to its answer, with a filter by level. */
function QaList({ body, onOpenAgent }: { body: string; onOpenAgent?: (id: string) => void }) {
  const qa = parseQa(parseBlocks(body));
  const [filter, setFilter] = useState("all");
  const [open, setOpen] = useState<Set<string>>(() => new Set(qa.items.slice(0, 1).map((q) => q.id)));
  const levels = Array.from(new Set(qa.items.map((q) => q.level).filter(Boolean)));
  const shown = qa.items.filter((q) => filter === "all" || q.level === filter);
  const toggle = (id: string) => setOpen((current) => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
  return (
    <div className="lh-qa">
      <Blocks blocks={qa.intro} onOpenAgent={onOpenAgent} />
      <div className="lh-qa-bar">
        <div className="lh-qa-filters" role="group" aria-label="Filter by level">
          {["all", ...levels].map((level) => (
            <button key={level} type="button" className={filter === level ? "on" : ""} aria-pressed={filter === level} onClick={() => setFilter(level)}>
              {level === "all" ? `All ${qa.items.length}` : LEVEL_LABEL[level] ?? level}
            </button>
          ))}
        </div>
        <button type="button" className="lh-qa-all" onClick={() => setOpen(open.size >= shown.length ? new Set() : new Set(shown.map((q) => q.id)))}>
          {open.size >= shown.length ? "Collapse all" : "Expand all"}
        </button>
      </div>
      <ol className="lh-qa-list">
        {shown.map((item, index) => {
          const isOpen = open.has(item.id);
          return (
            <li key={item.id} className={`lh-qa-item${isOpen ? " open" : ""}`}>
              <button type="button" className="lh-qa-q" aria-expanded={isOpen} onClick={() => toggle(item.id)}>
                <span className="lh-qa-n">{index + 1}</span>
                <span className="lh-qa-text">{renderInline(item.question, item.id)}</span>
                {item.level && <span className={`lh-level lv-${item.level}`}>{LEVEL_LABEL[item.level] ?? item.level}</span>}
                <span className="lh-qa-chevron" aria-hidden="true">▾</span>
              </button>
              {isOpen && <div className="lh-qa-a"><Blocks blocks={item.blocks} onOpenAgent={onOpenAgent} /></div>}
            </li>
          );
        })}
      </ol>
      <Blocks blocks={qa.footer} onOpenAgent={onOpenAgent} />
    </div>
  );
}

export default function LessonBody({ body, kind, onOpenAgent }: LessonBodyProps) {
  if (kind === "qa") return <QaList key={body} body={body} onOpenAgent={onOpenAgent} />;
  return <div className="lh-prose"><Blocks blocks={parseBlocks(body)} onOpenAgent={onOpenAgent} /></div>;
}
