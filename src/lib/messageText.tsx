import type { ReactNode } from "react";

/** Renders one line's inline markup: [links](https://...), **bold** and `code`.
 * Always React text nodes / elements, never raw HTML. */
function renderInlineMessageText(text: string): ReactNode[] {
  return text.split(/(\[[^\]]+\]\(https?:\/\/[^)]+\)|\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean).map((part, index) => {
    const markdownLink = part.match(/^\[([^\]]+)\]\((https?:\/\/[^)]+)\)$/);
    if (markdownLink) return <a key={index} href={markdownLink[2]} target="_blank" rel="noreferrer">{markdownLink[1]}</a>;
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={index}>{part.slice(1, -1)}</code>;
    return <span key={index}>{part}</span>;
  });
}

function renderTextBlock(text: string, keyPrefix: string): ReactNode[] {
  // Decode only display escapes; message text remains React text, never raw HTML.
  const lines = text.replace(/\\n/g, "\n").replace(/\\([@[\]()])/g, "$1").split("\n");
  return lines.map((line, index) => {
    const key = `${keyPrefix}-${index}`;
    const bullet = line.match(/^\s*[-*]\s+(.+)$/);
    const numbered = line.match(/^\s*(\d+)\.\s+(.+)$/);
    const heading = line.match(/^\s*#{1,3}\s+(.+)$/);
    if (heading) return <div className="message-heading" key={key}>{renderInlineMessageText(heading[1])}</div>;
    if (bullet) return <div className="message-list-item" key={key}>• {renderInlineMessageText(bullet[1])}</div>;
    if (numbered) return <div className="message-list-item" key={key}>{numbered[1]}. {renderInlineMessageText(numbered[2])}</div>;
    return <div key={key}>{line ? renderInlineMessageText(line) : " "}</div>;
  });
}

// ```optional-language\n ...verbatim... \n```
const FENCED_BLOCK = /```[^\n]*\n([\s\S]*?)\n?```/g;

/** Renders an agent/user message.
 *
 * Fenced code blocks are pulled out FIRST and shown verbatim in a monospace
 * block: no markdown, no escape decoding, exact spacing. That is what lets a
 * syntax error be shown the way a terminal prints it -- the offending line with
 * a caret under the column -- and keeps a source line such as `print("hi\n"`
 * from having its `\n` turned into a real line break. Everything outside the
 * fences is the usual headings / bullets / numbered items / inline markup. */
export function renderMessageText(text: string): ReactNode {
  const normalized = text.replace(/\r\n?/g, "\n");
  // split() with one capture group alternates: text, code, text, code, ...
  const segments = normalized.split(FENCED_BLOCK);
  // No fences: exactly the plain rendering every message has always had.
  if (segments.length === 1) return renderTextBlock(normalized, "text-0");

  const nodes: ReactNode[] = [];
  segments.forEach((segment, index) => {
    if (index % 2 === 1) {
      nodes.push(<pre className="message-code" key={`code-${index}`}><code>{segment}</code></pre>);
    } else if (segment.trim() !== "") {
      // The blank lines that separate a paragraph from the fence next to it
      // are layout, not content -- the block's own margin does that job.
      nodes.push(...renderTextBlock(segment.replace(/^\n+|\n+$/g, ""), `text-${index}`));
    }
  });
  return nodes;
}
