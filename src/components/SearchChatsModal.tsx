import { useEffect, useMemo, useRef, useState } from "react";
import type { Chat } from "../types";
import { DEFAULT_AGENT, findAgent } from "../data/agents";

interface Props {
  chats: Chat[];
  onOpenChat: (chatId: string) => void;
  onClose: () => void;
}

interface Hit {
  chat: Chat;
  snippet: string | null;
}

const RECENT_LIMIT = 8;
const RESULT_LIMIT = 30;

function snippetAround(text: string, index: number, length: number): string {
  const start = Math.max(0, index - 40);
  const end = Math.min(text.length, index + length + 70);
  return `${start > 0 ? "…" : ""}${text.slice(start, end).replace(/\s+/g, " ")}${end < text.length ? "…" : ""}`;
}

function search(chats: Chat[], query: string): Hit[] {
  const sorted = [...chats].sort((a, b) => Number(!!b.pinned) - Number(!!a.pinned) || b.updatedAt - a.updatedAt);
  const q = query.trim().toLowerCase();
  if (!q) return sorted.slice(0, RECENT_LIMIT).map((chat) => ({ chat, snippet: null }));
  const hits: Hit[] = [];
  for (const chat of sorted) {
    if (chat.title.toLowerCase().includes(q)) {
      hits.push({ chat, snippet: null });
      continue;
    }
    for (const message of chat.messages) {
      const at = message.text.toLowerCase().indexOf(q);
      if (at >= 0) {
        hits.push({ chat, snippet: snippetAround(message.text, at, q.length) });
        break;
      }
    }
    if (hits.length >= RESULT_LIMIT) break;
  }
  return hits;
}

function highlight(text: string, query: string) {
  const q = query.trim();
  if (!q) return text;
  const at = text.toLowerCase().indexOf(q.toLowerCase());
  if (at < 0) return text;
  return (
    <>
      {text.slice(0, at)}
      <mark>{text.slice(at, at + q.length)}</mark>
      {text.slice(at + q.length)}
    </>
  );
}

function timeAgo(ts: number): string {
  const minutes = Math.floor((Date.now() - ts) / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(ts).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export default function SearchChatsModal({ chats, onOpenChat, onClose }: Props) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLUListElement>(null);
  const hits = useMemo(() => search(chats, query), [chats, query]);

  useEffect(() => setActive(0), [query]);
  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(".sc-item.active")?.scrollIntoView?.({ block: "nearest" });
  }, [active]);

  function open(hit: Hit | undefined) {
    if (!hit) return;
    onOpenChat(hit.chat.id);
    onClose();
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") onClose();
    else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(hits.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      open(hits[active]);
    }
  }

  return (
    <div className="sc-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sc-card" role="dialog" aria-modal="true" aria-label="Search chats" onKeyDown={onKeyDown}>
        <div className="sc-input">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
            <path d="M21 21l-4.3-4.3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <input autoFocus value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search chats…" aria-label="Search chats" />
          <button type="button" className="sc-close" aria-label="Close search" onClick={onClose}>Esc</button>
        </div>

        <div className="sc-body">
          <div className="sc-heading">{query.trim() ? `${hits.length} result${hits.length === 1 ? "" : "s"}` : "Recent chats"}</div>
          {hits.length === 0 ? (
            <p className="sc-empty">{chats.length === 0 ? "No chats yet. Start a new chat to see it here." : `No chats found for “${query.trim()}”.`}</p>
          ) : (
            <ul ref={listRef} className="sc-list">
              {hits.map((hit, i) => {
                const agent = findAgent(hit.chat.agentId) ?? DEFAULT_AGENT;
                return (
                  <li key={hit.chat.id}>
                    <button
                      type="button"
                      className={`sc-item${i === active ? " active" : ""}`}
                      onMouseEnter={() => setActive(i)}
                      onClick={() => open(hit)}
                    >
                      <span className="sc-icon" style={{ background: `color-mix(in srgb, ${agent.color} 28%, transparent)` }}>{agent.icon}</span>
                      <span className="sc-main">
                        <b>{highlight(hit.chat.title || "Untitled chat", query)}{hit.chat.pinned && <em> 📌</em>}</b>
                        <small>{hit.snippet ? highlight(hit.snippet, query) : agent.name}</small>
                      </span>
                      <span className="sc-time">{timeAgo(hit.chat.updatedAt)}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
