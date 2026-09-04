export const WRITING_GOALS = {
  easy: { minWords: 60, maxWords: 90, minutes: 8, tone: "Clear and friendly", focus: "Complete sentences with simple reasons" },
  medium: { minWords: 90, maxWords: 140, minutes: 12, tone: "Organized and confident", focus: "Paragraph structure with examples" },
  hard: { minWords: 140, maxWords: 220, minutes: 18, tone: "Precise and thoughtful", focus: "Developed argument with specific detail" },
};

export function getWritingGoal({ mode, difficulty, topicTitle, prompt, turnNumber }) {
  const base = WRITING_GOALS[difficulty] || WRITING_GOALS.easy;
  const requiredPoints =
    mode === "topic"
      ? ["Answer the prompt directly", "Use topic-specific details", "Add one example or reason"]
      : ["Answer naturally", "Include one personal detail", "End with a clear final idea"];
  return {
    topic: topicTitle || (mode === "topic" ? "Topic-wise Writing" : "Daily Writing Challenge"),
    promptNumber: turnNumber || 1,
    difficulty,
    expectedWordCount: `${base.minWords}-${base.maxWords} words`,
    minWords: base.minWords,
    maxWords: base.maxWords,
    suggestedTime: `${base.minutes} min`,
    targetTone: base.tone,
    skillFocus: base.focus,
    requiredPoints,
    prompt,
  };
}

export function getWritingStats(text, goal) {
  const trimmed = (text || "").trim();
  const words = trimmed ? trimmed.match(/\b[\w'-]+\b/g)?.length || 0 : 0;
  const characters = (text || "").length;
  const sentences = trimmed ? trimmed.split(/[.!?]+/).filter((item) => item.trim()).length : 0;
  const paragraphs = trimmed ? trimmed.split(/\n{2,}/).filter((item) => item.trim()).length : 0;
  const readingMinutes = Math.max(1, Math.ceil(words / 200));
  const minWords = goal?.minWords || 0;
  const maxWords = goal?.maxWords || 0;
  const progress = minWords ? Math.min(100, Math.round((words / minWords) * 100)) : 0;
  const status = !words
    ? "Start writing"
    : words < minWords
      ? `${minWords - words} words to suggested minimum`
      : maxWords && words > maxWords
        ? "Above the suggested range"
        : "On track";
  return { words, characters, sentences, paragraphs, readingMinutes, progress, status };
}

function countSyllables(word) {
  word = word.toLowerCase().replace(/[^a-z]/g, "");
  if (!word) return 0;
  const vowelGroups = word.match(/[aeiouy]+/g) || [];
  let count = vowelGroups.length;
  if (word.endsWith("e") && count > 1) count -= 1;
  return Math.max(count, 1);
}

export function getReadabilityGrade(text) {
  const words = text.trim() ? text.trim().split(/\s+/) : [];
  const sentences = (text.match(/[.!?]+/g) || []).length || 1;
  if (words.length === 0) return null;
  const syllables = words.reduce((sum, w) => sum + countSyllables(w), 0);
  const grade = 0.39 * (words.length / sentences) + 11.8 * (syllables / words.length) - 15.59;
  return Math.max(1, Math.round(grade));
}

export function analyzeSentenceIssues(text) {
  const PASSIVE_PATTERN = /\b(am|is|are|was|were|be|been|being)\s+\w+ed\b/gi;
  const ADVERB_PATTERN = /\b\w+ly\b/gi;
  
  const sentences = text.split(/(?<=[.!?])\s+/).filter(Boolean);
  return sentences.map((sentence) => {
    const wordCount = sentence.trim().split(/\s+/).filter(Boolean).length;
    PASSIVE_PATTERN.lastIndex = 0;
    ADVERB_PATTERN.lastIndex = 0;
    return {
      text: sentence,
      passive: PASSIVE_PATTERN.test(sentence),
      hasAdverb: ADVERB_PATTERN.test(sentence),
      hard: wordCount > 20 && wordCount <= 30,
      veryHard: wordCount > 30,
    };
  });
}
