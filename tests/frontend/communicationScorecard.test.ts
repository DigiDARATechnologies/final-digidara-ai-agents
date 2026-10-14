// The API module uses browser-only syntax; the formatter under test never calls it.
jest.mock("../../src/lib/communicationApi", () => ({}));

import { formatExecutiveScorecard } from "../../src/lib/communicationFlow";

test("a session with no answers shows no score at all", () => {
  const text = formatExecutiveScorecard({
    answered_turns: 0, overall_score: null, grammar_score: null,
    executive_scorecard: { scores_breakdown: null, you_did_well: null },
  });
  expect(text).toContain("no score yet");
  expect(text).toContain("You didn't answer any questions");
  expect(text).not.toMatch(/\d+\/100/);
  expect(text).not.toContain("You Did Well");
});

test("answers that could not be scored say so, with no number", () => {
  const text = formatExecutiveScorecard({ answered_turns: 2, overall_score: null, executive_scorecard: { scores_breakdown: null } });
  expect(text).toContain("could not be scored");
  expect(text).not.toMatch(/\d+\/100/);
});

test("only the scores that were given are shown, exactly as given", () => {
  const text = formatExecutiveScorecard({
    answered_turns: 1,
    executive_scorecard: { scores_breakdown: { overall: 35, grammar: 50, fluency: 30, confidence: 40 }, you_did_well: "You answered in full sentences." },
  });
  expect(text).toContain("**Overall:** 35/100");
  expect(text).toContain("**Grammar:** 50/100");
  expect(text).not.toContain("Vocabulary");
  expect(text).not.toContain("Sentence Structure");
  expect(text).toContain("1 answer scored");
});

test("without a breakdown, the session's own out-of-10 scores are used (0 included)", () => {
  const text = formatExecutiveScorecard({ answered_turns: 1, overall_score: 4.2, grammar_score: 0 });
  expect(text).toContain("**Overall:** 42/100");
  expect(text).toContain("**Grammar:** 0/100");
});
