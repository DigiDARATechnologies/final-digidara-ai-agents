export const VERDICT_LABELS = {
  correct: "Correct",
  partial: "Partially Correct",
  wrong: "Wrong",
};

export const AI_ASSESSMENT_CAPTION = (
  "The AI's holistic judgment of your interview, weighing technical "
  + "accuracy, communication clarity, and confidence."
);

export const HR_ASSESSMENT_CAPTION = (
  "The AI's holistic judgment of your interview, weighing answer relevance, "
  + "behavioral judgment, communication clarity, and confidence."
);

export function formatMarks(marks) {
  if (marks === null || marks === undefined) return "-";
  return marks % 1 === 0 ? String(marks) : marks.toFixed(1);
}
