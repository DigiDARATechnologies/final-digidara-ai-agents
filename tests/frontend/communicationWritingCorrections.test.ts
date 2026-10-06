// The API module uses browser-only syntax; the formatter under test never calls it.
jest.mock("../../src/lib/communicationApi", () => ({}));

import { writingCorrections } from "../../src/lib/communicationFlow";

test("every correction is shown as wrong -> right with its reason", () => {
  const text = writingCorrections({
    mistakes: [
      { incorrect: "He go to school", correct: "He goes to school", explanation: "A singular subject takes 'goes'." },
      { incorrect: "informations", correct: "information", explanation: "'Information' has no plural." },
    ],
  });
  expect(text).toContain("**Corrections (2):**");
  expect(text).toContain("❌ “He go to school” → ✅ “He goes to school”");
  expect(text).toContain("A singular subject takes 'goes'.");
  expect(text).toContain("❌ “informations” → ✅ “information”");
});

test("corrections given only as mistake_points are still shown", () => {
  const text = writingCorrections({
    mistakes: [],
    mistake_points: ['"I am agree" → "I agree" — "agree" is already a verb.'],
  });
  expect(text).toContain("**Corrections (1):**");
  expect(text).toContain("❌ “I am agree” → ✅ “I agree” — \"agree\" is already a verb.");
});

test("an answer with no mistakes says so instead of an empty list", () => {
  expect(writingCorrections({ mistakes: [], mistake_points: ["No grammar corrections needed for this response."] }))
    .toBe("**Corrections:** ✅ No grammar mistakes found.");
});

test("a 'correction' identical to the original is not listed, and duplicates appear once", () => {
  const text = writingCorrections({
    mistakes: [
      { incorrect: "I like tea.", correct: "I like tea" },
      { incorrect: "She don't", correct: "She doesn't" },
      { incorrect: "She don't", correct: "She doesn't" },
    ],
  });
  expect(text).toContain("**Corrections (1):**");
  expect(text).not.toContain("I like tea");
});

test("better word choices are listed after the corrections", () => {
  const text = writingCorrections({
    mistakes: [],
    vocabulary_suggestions: [{ original: "very good", suggestion: "excellent", example: "The result was excellent." }],
  });
  expect(text).toContain("**Better word choices:**\n• “very good” → “excellent”\n  e.g. The result was excellent.");
});
