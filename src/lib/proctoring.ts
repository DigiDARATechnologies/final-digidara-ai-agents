/** Rules shared by the proctoring screens (no network, so unit-testable). */
import type { LevelId } from "./learnerApi";
import type { ProctorSettings } from "./proctorApi";

/** Hard and Professional mock interviews and capstone vivas are proctored. */
export const PROCTORED_LEVELS: readonly string[] = ["hard", "professional"];

/** Mock interview difficulty "advanced" is the Hard and Professional levels. */
export function mockInterviewProctored(difficulty: string | undefined): boolean {
  return difficulty === "advanced";
}

/** Capstone difficulty is easy / medium / hard / professional. */
export function vivaProctored(difficulty: string | undefined): boolean {
  return PROCTORED_LEVELS.includes(difficulty ?? "");
}

export function levelProctored(level: LevelId): boolean {
  return PROCTORED_LEVELS.includes(level);
}

export const EVENT_LABELS: Record<string, string> = {
  focus_lost: "Left the test tab or window",
  fullscreen_exit: "Left full screen",
  copy: "Tried to copy",
  cut: "Tried to cut",
  paste: "Tried to paste",
  context_menu: "Opened the right-click menu",
  camera_off: "Camera turned off",
  camera_blocked: "Camera not allowed",
  no_face: "No face in the camera",
  multiple_faces: "More than one face in the camera",
  phone: "Phone or second screen seen",
  session_resumed: "Reloaded or reopened the test",
};

/** The rules shown on the consent screen, one line per check that is on. */
export function ruleLines(settings: ProctorSettings): string[] {
  const lines: string[] = [];
  if (settings.fullscreen) lines.push("The test runs in full screen. Leaving full screen is a warning.");
  if (settings.tab) lines.push("Stay on this tab. Switching tabs or windows is a warning.");
  if (settings.copy_paste) lines.push("Copy, paste and right-click are turned off and recorded.");
  if (settings.webcam) lines.push("Your camera stays on. A small photo is taken about once a minute.");
  if (settings.face) lines.push("Photos are checked for your face, other people and phones.");
  lines.push(`After ${settings.max_warnings} warning${settings.max_warnings === 1 ? "" : "s"}, the next one ends the test.`);
  return lines;
}

/** "Score 7 / 10" style text for a proctored result. */
export function resultText(result: { score?: number | null; max?: number | null; label?: string | null; passed?: boolean; percent?: number } | null): string {
  if (!result) return "-";
  if (result.label) return `${result.label}${result.passed === undefined ? "" : result.passed ? " (passed)" : " (not passed)"}`;
  if (result.percent != null && result.score != null && result.max != null) return `${result.score} / ${result.max} (${Math.round(result.percent)}%)`;
  if (result.score != null && result.max != null) return `${Number(result.score).toFixed(Number.isInteger(result.score) ? 0 : 1)} / ${result.max}`;
  return "-";
}

export function integrityBand(score: number): "good" | "fair" | "poor" {
  return score >= 80 ? "good" : score >= 50 ? "fair" : "poor";
}

/** An assessment the learner just started on the link's page, handed to
 * the Mock Interview chat that runs it. */
export interface AssessmentLaunch {
  sessionId: string;
  title: string;
  config: { round_type: "technical" | "hr"; role_name: string; subject: string; num_questions: 5 | 10 | 15; level: LevelId };
}

/** What starting an assessment link leads to: a Mock Interview chat, or a knowledge test screen. */
export type AssessmentStart =
  | ({ kind: "mock_interview" } & AssessmentLaunch)
  | { kind: "knowledge_test"; sessionId: string; title: string };

let pendingLaunch: AssessmentLaunch | null = null;
const freshSessions = new Set<string>();

export function setAssessmentLaunch(launch: AssessmentLaunch): void {
  pendingLaunch = launch;
  freshSessions.add(launch.sessionId);
}

/** An attempt the learner just started and agreed to on the link's page. */
export function markFreshSession(sessionId: string): void {
  freshSessions.add(sessionId);
}

export function takeAssessmentLaunch(): AssessmentLaunch | null {
  const launch = pendingLaunch;
  pendingLaunch = null;
  return launch;
}

/** True once for an attempt started on the link's page in this tab (the
 * learner already agreed there). A reload makes it false: the test then
 * continues through the consent screen and counts as reopened. */
export function isFreshSession(sessionId: string): boolean {
  return freshSessions.has(sessionId);
}

/** Proctoring for that attempt has started: a later reopen goes through consent. */
export function forgetFreshSession(sessionId: string): void {
  freshSessions.delete(sessionId);
}

/** Mock interview difficulty for a level. */
export function levelDifficulty(level: LevelId): "beginner" | "intermediate" | "advanced" {
  return level === "beginner" ? "beginner" : level === "medium" ? "intermediate" : "advanced";
}

/** A server time for people: "24 Oct 2026, 3:05 pm", or "-". */
export function formatWhen(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "-";
}
