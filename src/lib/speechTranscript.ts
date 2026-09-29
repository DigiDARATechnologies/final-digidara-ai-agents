export interface SpeechResultSnapshot {
  text: string;
  isFinal: boolean;
}

export interface SpeechResultEventSnapshot {
  resultIndex: number;
  results: ArrayLike<{
    isFinal: boolean;
    0: { transcript: string };
  }>;
}

function words(value: string): string[] {
  return value.trim().split(/\s+/).filter(Boolean);
}

/**
 * Joins Web Speech result slots without compounding cumulative results.
 * Mobile implementations sometimes publish the complete phrase again in a
 * later slot instead of publishing only the new words.
 */
export function joinSpeechSegments(segments: string[]): string {
  let assembled: string[] = [];
  for (const value of segments) {
    const incoming = words(value);
    if (!incoming.length) continue;
    if (!assembled.length) {
      assembled = incoming;
      continue;
    }

    const existingLower = assembled.map((word) => word.toLocaleLowerCase());
    const incomingLower = incoming.map((word) => word.toLocaleLowerCase());
    const existingText = existingLower.join(" ");
    const incomingText = incomingLower.join(" ");

    // A mobile recognizer may replace a short result with a longer cumulative
    // result, or replay a result that is already present.
    if (incomingText === existingText || existingText.endsWith(` ${incomingText}`)) continue;
    if (incomingText.startsWith(`${existingText} `)) {
      assembled = incoming;
      continue;
    }

    let overlap = 0;
    const maximum = Math.min(assembled.length, incoming.length);
    for (let size = maximum; size >= 2; size -= 1) {
      const tail = existingLower.slice(-size).join(" ");
      const head = incomingLower.slice(0, size).join(" ");
      if (tail === head) {
        overlap = size;
        break;
      }
    }
    assembled.push(...incoming.slice(overlap));
  }
  return assembled.join(" ").trim();
}

/** Updates only the result indices reported as changed and rebuilds display
 * and final transcripts from those slots. Re-emitting an existing mobile
 * result index replaces that slot instead of appending it again. */
export function updateSpeechResultSlots(
  slots: Map<number, SpeechResultSnapshot>,
  event: SpeechResultEventSnapshot,
) {
  for (const index of [...slots.keys()]) {
    if (index >= event.results.length) slots.delete(index);
  }
  const startIndex = Math.max(0, Math.min(event.resultIndex, event.results.length));
  for (let index = startIndex; index < event.results.length; index += 1) {
    const result = event.results[index];
    slots.set(index, {
      text: String(result[0]?.transcript || "").trim(),
      isFinal: Boolean(result.isFinal),
    });
  }
  const ordered = [...slots.entries()].sort(([left], [right]) => left - right).map(([, result]) => result);
  return {
    displayText: joinSpeechSegments(ordered.map((result) => result.text)),
    finalText: joinSpeechSegments(ordered.filter((result) => result.isFinal).map((result) => result.text)),
    interimText: joinSpeechSegments(ordered.filter((result) => !result.isFinal).map((result) => result.text)),
  };
}
