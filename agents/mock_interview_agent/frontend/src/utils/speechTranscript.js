function words(value) {
  return String(value || "").trim().split(/\s+/).filter(Boolean);
}

export function joinSpeechSegments(segments) {
  let assembled = [];
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
    if (incomingText === existingText || existingText.endsWith(` ${incomingText}`)) continue;
    if (incomingText.startsWith(`${existingText} `)) {
      assembled = incoming;
      continue;
    }
    let overlap = 0;
    for (let size = Math.min(assembled.length, incoming.length); size >= 2; size -= 1) {
      if (existingLower.slice(-size).join(" ") === incomingLower.slice(0, size).join(" ")) {
        overlap = size;
        break;
      }
    }
    assembled.push(...incoming.slice(overlap));
  }
  return assembled.join(" ").trim();
}

export function updateSpeechResultSlots(slots, event) {
  for (const index of [...slots.keys()]) {
    if (index >= event.results.length) slots.delete(index);
  }
  const startIndex = Math.max(0, Math.min(event.resultIndex, event.results.length));
  for (let index = startIndex; index < event.results.length; index += 1) {
    slots.set(index, {
      text: String(event.results[index][0]?.transcript || "").trim(),
      isFinal: Boolean(event.results[index].isFinal),
    });
  }
  const ordered = [...slots.entries()].sort(([left], [right]) => left - right).map(([, result]) => result);
  return {
    displayText: joinSpeechSegments(ordered.map((result) => result.text)),
    finalText: joinSpeechSegments(ordered.filter((result) => result.isFinal).map((result) => result.text)),
    interimText: joinSpeechSegments(ordered.filter((result) => !result.isFinal).map((result) => result.text)),
  };
}
