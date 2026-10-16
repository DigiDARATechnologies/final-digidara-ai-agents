/**
 * What the learner tells Boss to do, recognised here rather than left to the
 * model: "open aptitude", "switch to mock interview", "go back to Boss chat",
 * "close the tab". The model forgot its action tag once a conversation already
 * held an "Opening ..." reply, so a second switch did nothing; recognised here,
 * every switch and every close works, by voice or typed, in the Boss panel and
 * in the Boss chat's voice conversation alike.
 */
import { withoutWakeWords } from "./assistText";

/** Where Boss can take the learner: the browser's agent ids, and pages. */
export const BOSS_TARGETS: Record<string, string> = {
  leetcode: "Coding Practice",
  aptitude: "Aptitude Trainer",
  "mock-interview": "Mock Interview",
  "communication-coach": "Communication Coach",
  "resume-builder": "Resume Builder",
  "capstone-project": "Capstone Project",
  "certificate-agent": "AI Certification",
  "job-fetch": "Job Agent",
  boss: "Boss chat",
  readiness: "Job Readiness",
};

// Most specific first: "mock interview" before "interview", "job readiness" before "job".
const ALIASES: Array<[RegExp, string]> = [
  [/^(?:the\s+)?mock\s*interview(?:er)?$|^interview(?:\s+practice)?$/, "mock-interview"],
  [/^(?:the\s+)?(?:job\s+)?readiness(?:\s+(?:score|report))?$|^(?:my\s+)?progress$/, "readiness"],
  [/^(?:the\s+)?(?:coding(?:\s+practice)?|code\s*forge|leet\s*code|programming|dsa)$/, "leetcode"],
  [/^(?:the\s+)?aptitude(?:\s+(?:trainer|test|practice))?$/, "aptitude"],
  [/^(?:the\s+)?communication(?:\s+(?:coach|practice))?$|^english\s+(?:coach|practice)$/, "communication-coach"],
  [/^(?:the\s+)?(?:resume|cv)(?:\s+builder)?$/, "resume-builder"],
  [/^(?:the\s+)?capstone(?:\s+projects?)?$|^projects?$/, "capstone-project"],
  [/^(?:the\s+)?(?:ai\s+)?certification$|^certify\s*ai$|^certificate\s+agent$/, "certificate-agent"],
  [/^(?:the\s+)?(?:jobs?|job\s+(?:search|fetch|finder))$/, "job-fetch"],
  [/^(?:the\s+)?(?:boss(?:\s+chat)?|home|main\s+chat|general\s+chat|new\s+chat)$/, "boss"],
];

const POLITE = String.raw`(?:(?:ok(?:ay)?|please|now|and|then|also|so|boss|can\s+you|could\s+you|will\s+you|i\s+want\s+to|i\s+wanna|let'?s)[\s,]+)*`;
const VERB = String.raw`(?:open(?:\s+up)?|switch(?:\s+(?:me|over))?\s+to|change\s+to|go(?:\s+back)?\s+to|goto|take\s+me(?:\s+back)?\s+to|move\s+to|navigate\s+to|bring\s+up|launch|show(?:\s+me)?)`;
const TAIL = String.raw`(?:\s+(?:agent|page|tab|screen|section|chat|one))?(?:[\s,]+(?:please|boss|now|for\s+me|again))*`;
// "Open aptitude", "switch to the mock interview agent please".
const COMMAND = new RegExp(String.raw`^${POLITE}${VERB}\s+(?:the\s+|my\s+)?(.+?)${TAIL}$`, "i");
// Tamil/Hindi-English: "aptitude open pannu", "mock interview ku po", "resume kholo".
const AFTER = new RegExp(String.raw`^${POLITE}(?:the\s+)?(.+?)${TAIL}\s+(?:open(?:\s+(?:pannu|pannunga|karo|kar\s+do))?|ku\s+po(?:nga)?|kholo)$`, "i");

/** "Close the tab", "please close Boss", "you can close this": Boss closes. */
export const CLOSE_PHRASE = /^(?:(?:ok(?:ay)?|please|now)[\s,]+)*(?:you\s+can\s+|can\s+you\s+)?(?:close|exit|hide|shut)(?:\s+(?:(?:the|this|that|your)\s+)?(?:tab|panel|window|boss|chat|assistant|it|this|yourself)(?:\s+(?:tab|panel|window))?)?(?:[\s,]+(?:please|boss))*[\s.!]*$/i;

export type BossCommand = { type: "open"; target: string; label: string } | { type: "close" };

function targetFor(name: string): string | null {
  const words = name.toLowerCase().replace(/[.!?]+$/, "").replace(/\s+/g, " ").trim();
  for (const [pattern, target] of ALIASES) if (pattern.test(words)) return target;
  return null;
}

/** The command in what the learner said, or null when it is a question for Boss. */
export function parseBossCommand(said: string): BossCommand | null {
  const text = withoutWakeWords(said).replace(/[.!?]+$/, "").trim();
  if (!text) return null;
  if (CLOSE_PHRASE.test(text)) return { type: "close" };
  const match = COMMAND.exec(text) || AFTER.exec(text);
  const target = match ? targetFor(match[1]) : null;
  return target ? { type: "open", target, label: BOSS_TARGETS[target] } : null;
}

/** What Boss says as it goes there. */
export function openingLine(label: string): string {
  return `Opening ${label}.`;
}
