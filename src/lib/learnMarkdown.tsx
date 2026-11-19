/** A small, safe Markdown reader for Learning Hub lessons.
 *
 * Lessons are our own files, but the text is still never put in the page as HTML: it is parsed into
 * blocks and drawn as React elements, so a stray "<script>" in a lesson is shown as text.
 *
 * Supported: ## and ### headings, paragraphs, - and 1. lists, fenced code (```lang; "output" is a result box),
 * pipe tables, --- rules, and :::type callouts (tip, note, warning, remember, formula, example, trick,
 * interview, practice) that hold more blocks. Inline: `code`, **bold**, *italic*, [links](https://...).
 */
import type { ReactNode } from "react";

export type Block =
  | { t: "h"; level: 2 | 3; text: string; id: string }
  | { t: "p"; text: string }
  | { t: "list"; ordered: boolean; items: string[] }
  | { t: "code"; lang: string; code: string }
  | { t: "table"; head: string[]; rows: string[][] }
  | { t: "callout"; kind: string; arg: string; blocks: Block[] }
  | { t: "hr" };

export const CALLOUT_KINDS = ["tip", "note", "warning", "remember", "formula", "example", "trick", "interview", "practice"] as const;

export function slugify(text: string): string {
  return text.toLowerCase().replace(/[`*]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "section";
}

/** Split a table row on | but not inside `code`. */
function cells(line: string): string[] {
  const out: string[] = [];
  let current = "";
  let inCode = false;
  for (const ch of line.trim().replace(/^\|/, "").replace(/\|$/, "")) {
    if (ch === "`") inCode = !inCode;
    if (ch === "|" && !inCode) { out.push(current.trim()); current = ""; } else current += ch;
  }
  out.push(current.trim());
  return out;
}

const isTableDivider = (line: string) => /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/.test(line);
const CALLOUT_OPEN = /^:::([a-z]+)(?:[ \t]+(.*))?$/;

export function parseBlocks(source: string): Block[] {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  const used = new Map<string, number>();
  let i = 0;

  const uniqueId = (text: string) => {
    const base = slugify(text);
    const count = used.get(base) ?? 0;
    used.set(base, count + 1);
    return count ? `${base}-${count + 1}` : base;
  };

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }

    const fence = /^```\s*([A-Za-z0-9_+-]*)\s*$/.exec(line);
    if (fence) {
      const body: string[] = [];
      i++;
      while (i < lines.length && !/^```\s*$/.test(lines[i])) body.push(lines[i++]);
      i++;
      blocks.push({ t: "code", lang: fence[1].toLowerCase(), code: body.join("\n") });
      continue;
    }

    const callout = CALLOUT_OPEN.exec(line);
    if (callout) {
      const inner: string[] = [];
      i++;
      let inFence = false;
      while (i < lines.length && (inFence || !/^:::\s*$/.test(lines[i]))) {
        if (/^```/.test(lines[i])) inFence = !inFence;
        inner.push(lines[i++]);
      }
      i++;
      blocks.push({ t: "callout", kind: callout[1], arg: (callout[2] ?? "").trim(), blocks: parseBlocks(inner.join("\n")) });
      continue;
    }

    const heading = /^(#{2,3})\s+(.+?)\s*#*\s*$/.exec(line);
    if (heading) {
      const text = heading[2].trim();
      blocks.push({ t: "h", level: heading[1].length === 2 ? 2 : 3, text, id: uniqueId(text) });
      i++;
      continue;
    }

    if (/^---+\s*$/.test(line)) { blocks.push({ t: "hr" }); i++; continue; }

    if (line.trimStart().startsWith("|") && i + 1 < lines.length && isTableDivider(lines[i + 1])) {
      const head = cells(line);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trimStart().startsWith("|")) rows.push(cells(lines[i++]));
      blocks.push({ t: "table", head, rows });
      continue;
    }

    const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    if (bullet || numbered) {
      const ordered = Boolean(numbered);
      const items: string[] = [];
      while (i < lines.length) {
        const m = (ordered ? /^\s*\d+[.)]\s+(.*)$/ : /^\s*[-*]\s+(.*)$/).exec(lines[i]);
        if (!m) break;
        items.push(m[1]);
        i++;
      }
      blocks.push({ t: "list", ordered, items });
      continue;
    }

    const paragraph: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(```|:::|#{2,3}\s|---+\s*$)/.test(lines[i])
      && !(lines[i].trimStart().startsWith("|") && i + 1 < lines.length && isTableDivider(lines[i + 1]))
      && !/^\s*([-*]|\d+[.)])\s+/.test(lines[i])) {
      paragraph.push(lines[i++].trim());
    }
    if (paragraph.length) blocks.push({ t: "p", text: paragraph.join(" ") });
    else i++;
  }
  return blocks;
}

/** Only web links and in-site paths are allowed; anything else (javascript:, data:) is shown as plain text. */
export function safeHref(href: string): string | null {
  const value = href.trim();
  if (/^https?:\/\//i.test(value)) return value;
  if (/^\/(?!\/)/.test(value)) return value;
  return null;
}

const INLINE = /(`[^`\n]+`)|(\*\*[^*\n]+\*\*)|(\*[^*\s][^*\n]*\*)|(\[[^\]\n]+\]\([^)\s]+\))/g;

export function renderInline(text: string, keyPrefix = "i"): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let n = 0;
  for (const match of text.matchAll(INLINE)) {
    const start = match.index ?? 0;
    if (start > last) out.push(text.slice(last, start));
    const token = match[0];
    const key = `${keyPrefix}${n++}`;
    if (match[1]) out.push(<code key={key}>{token.slice(1, -1)}</code>);
    else if (match[2]) out.push(<strong key={key}>{renderInline(token.slice(2, -2), `${key}s`)}</strong>);
    else if (match[3]) out.push(<em key={key}>{renderInline(token.slice(1, -1), `${key}e`)}</em>);
    else {
      const link = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(token);
      const href = link ? safeHref(link[2]) : null;
      if (link && href) out.push(<a key={key} href={href} target={href.startsWith("http") ? "_blank" : undefined} rel="noopener noreferrer">{link[1]}</a>);
      else out.push(link ? link[1] : token);
    }
    last = start + token.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** The ## headings of a lesson, for the "On this page" outline. */
export function outlineOf(blocks: Block[]): { id: string; text: string }[] {
  return blocks.filter((b): b is Extract<Block, { t: "h" }> => b.t === "h" && b.level === 2).map((b) => ({ id: b.id, text: b.text }));
}

export interface QaItem { level: string; question: string; id: string; blocks: Block[] }
export interface QaLesson { intro: Block[]; items: QaItem[]; footer: Block[] }

const QA_HEADING = /^Q\s*(?:\[(Easy|Medium|Hard)\])?\s*(.+)$/i;

/** An interview-question lesson: "### Q [Medium] Question" starts each item; callouts at the end are the footer. */
export function parseQa(blocks: Block[]): QaLesson {
  const intro: Block[] = [];
  const items: QaItem[] = [];
  let current: QaItem | null = null;
  for (const block of blocks) {
    if (block.t === "h" && block.level === 3) {
      const match = QA_HEADING.exec(block.text);
      if (match) {
        current = { level: (match[1] ?? "").toLowerCase(), question: match[2].trim(), id: block.id, blocks: [] };
        items.push(current);
        continue;
      }
    }
    (current ? current.blocks : intro).push(block);
  }
  const footer: Block[] = [];
  const last = items[items.length - 1];
  while (last && last.blocks.length && last.blocks[last.blocks.length - 1].t === "callout") footer.unshift(last.blocks.pop() as Block);
  return { intro, items, footer };
}

/** Plain text of a block list, for copying or search snippets. */
export function plainText(blocks: Block[]): string {
  return blocks.map((b) => {
    if (b.t === "p") return b.text;
    if (b.t === "h") return b.text;
    if (b.t === "list") return b.items.join("\n");
    if (b.t === "code") return b.code;
    if (b.t === "callout") return plainText(b.blocks);
    return "";
  }).join("\n");
}
