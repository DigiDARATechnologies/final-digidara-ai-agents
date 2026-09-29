import { describe, expect, test } from "vitest";
import { updateSpeechResultSlots } from "../utils/speechTranscript";

function event(resultIndex, inputs) {
  return {
    resultIndex,
    results: inputs.map(({ text, final }) => ({ isFinal: final, 0: { transcript: text } })),
  };
}

describe("mobile speech transcript assembly", () => {
  test("replaces repeated result indices instead of appending them", () => {
    const slots = new Map();
    updateSpeechResultSlots(slots, event(0, [{ text: "variable", final: false }]));
    updateSpeechResultSlots(slots, event(0, [{ text: "variable is", final: false }]));
    const result = updateSpeechResultSlots(slots, event(0, [{ text: "A variable stores a value", final: true }]));
    expect(result.finalText).toBe("A variable stores a value");
  });

  test("collapses cumulative or replayed final phrases", () => {
    const slots = new Map();
    const result = updateSpeechResultSlots(slots, event(0, [
      { text: "The view in Django", final: true },
      { text: "The view in Django handles requests", final: true },
      { text: "The view in Django handles requests", final: true },
    ]));
    expect(result.finalText).toBe("The view in Django handles requests");
  });
});
