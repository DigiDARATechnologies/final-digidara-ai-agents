/** Turning agent replies into speakable, sentence-sized pieces (no network,
 * so it is unit-testable). */
const MAX_CHUNK = 260;
// The first piece is short, so the first words are heard sooner.
const FIRST_CHUNK = 140;

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

/** Sentence-sized chunks, joining short sentences up to MAX_CHUNK. */
export function splitForSpeech(text: string): string[] {
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
    const limit = chunks.length === 0 ? FIRST_CHUNK : MAX_CHUNK;
    if (current && current.length + sentence.length + 1 > limit) {
      chunks.push(current);
      current = sentence;
    } else {
      current = current ? `${current} ${sentence}` : sentence;
    }
  }
  if (current) chunks.push(current);
  return chunks;
}
