/** Turning agent replies into speakable, sentence-sized pieces (no network,
 * so it is unit-testable). */
const MAX_CHUNK = 260;
// The first piece is short -- generation time grows with length -- so the
// first words are heard sooner while the rest is generated behind it.
const FIRST_CHUNK = 100;

/** Text as it should be heard: no markdown, links, code or emoji. */
export function speakableText(raw: string): string {
  return (raw || "")
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/https?:\/\/\S+/g, " ")
    .replace(/^\s{0,3}(#{1,6}|>|[-*+]|\d+[.)])\s+/gm, "")
    .replace(/[*_~|]+/g, "")
    .replace(/\p{Extended_Pictographic}/gu, "")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * The finished sentences of a reply that is still being written, after
 * character `from`: everything up to the last sentence end (. ! ? after a
 * word, followed by a space) or line break. `next` is where to look next
 * time; an unfinished sentence waits for more text.
 */
export function completeSentences(text: string, from: number): { text: string; next: number } {
  const rest = text.slice(from);
  let end = -1;
  for (const match of rest.matchAll(/(?<=[\p{L})"'”’])[.!?।]+["”’)]*(?=\s)|\n/gu)) {
    end = (match.index ?? 0) + match[0].length;
  }
  return end < 0 ? { text: "", next: from } : { text: rest.slice(0, end), next: from + end };
}

/** Sentence-sized chunks, joining short sentences up to MAX_CHUNK.
 * `shortFirst`: make the first chunk short so speech starts sooner -- only
 * for the start of a reply; later text is never cut mid-sentence. */
export function splitForSpeech(text: string, shortFirst = true): string[] {
  const sentences = text.match(/[^.!?।\n]+[.!?।]*\s*/g) ?? [text];
  const chunks: string[] = [];
  let current = "";
  for (const raw of sentences) {
    const sentence = raw.trim();
    if (!sentence) continue;
    if (sentence.length > MAX_CHUNK) {
      if (current) { chunks.push(current); current = ""; }
      // A very long sentence: split at commas, then hard-wrap.
      for (const piece of sentence.split(/(?<=[,;:])\s+/)) {
        let rest = piece;
        while (rest.length > MAX_CHUNK) {
          const cut = rest.lastIndexOf(" ", MAX_CHUNK);
          chunks.push(rest.slice(0, cut > 40 ? cut : MAX_CHUNK));
          rest = rest.slice(cut > 40 ? cut + 1 : MAX_CHUNK);
        }
        if (rest) chunks.push(rest);
      }
      continue;
    }
    // Keep the first chunk short so speech starts fast.
    const limit = chunks.length === 0 && shortFirst ? FIRST_CHUNK : MAX_CHUNK;
    if (current && current.length + sentence.length + 1 > limit) {
      chunks.push(current);
      current = sentence;
    } else {
      current = current ? `${current} ${sentence}` : sentence;
    }
  }
  if (current) chunks.push(current);
  // A long first sentence: speak its opening clause first.
  if (shortFirst && chunks.length && chunks[0].length > FIRST_CHUNK) {
    const first = chunks[0];
    const comma = first.lastIndexOf(", ", FIRST_CHUNK);
    const space = first.lastIndexOf(" ", FIRST_CHUNK);
    const cut = comma >= 40 ? comma + 1 : space >= 40 ? space : -1;
    if (cut > 0) chunks.splice(0, 1, first.slice(0, cut).trim(), first.slice(cut).trim());
  }
  return chunks;
}
