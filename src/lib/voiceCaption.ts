/** The words of a reply as a caption: markdown and links stripped, and only
 * the end of a long reply, so the caption follows what is being said. */
export function messageToSpeech(text: string, maxChars = 280): string {
  const plain = text
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[*_`#>]+/g, "")
    .replace(/\s+/g, " ")
    .trim();
  if (plain.length <= maxChars) return plain;
  const tail = plain.slice(-maxChars);
  const start = tail.indexOf(" ");
  return `…${start > 0 ? tail.slice(start + 1) : tail}`;
}
