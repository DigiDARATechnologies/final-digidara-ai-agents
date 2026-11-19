/** Learning Hub (orchestrator app/learn): tutorials, interview questions and aptitude lessons.
 * Read with coins or a college licence; locked learners get a 402 with the reason. */
import { sessionToken } from "./session";

const RAW_BASE = import.meta.env.VITE_GATEWAY_API_URL !== undefined ? import.meta.env.VITE_GATEWAY_API_URL : "http://127.0.0.1:8100";
const BASE = RAW_BASE.endsWith("/") ? RAW_BASE.slice(0, -1) : RAW_BASE;

/** An API error that keeps the HTTP status, so the screen can tell "locked" (402) from a failure. */
export class LearnApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${sessionToken() || ""}`, ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : Array.isArray(body.detail) ? body.detail[0]?.msg : null;
    throw new LearnApiError(response.status, detail || "Something went wrong. Please try again.");
  }
  return response.json();
}

export type AccessReason = "admin" | "college" | "coins" | "no_purchase" | "no_coins";
export interface Access { unlocked: boolean; reason: AccessReason }

export type CourseStatus = "live" | "soon";
export interface CourseSummary {
  slug: string; title: string; track: string; level: string; summary: string; icon: string; color: string;
  status: CourseStatus; kind: "tutorial" | "qa"; lessons: number; chapters: number; minutes: number; completed: number;
}
export interface Track { id: string; title: string; blurb: string; courses: CourseSummary[] }
export interface LearningPath { id: string; title: string; summary: string; courses: CourseSummary[] }
export interface Catalog { access: Access; tracks: Track[]; paths: LearningPath[] }

export interface OutlineLesson { id: string; title: string; minutes: number; kind: string; done: boolean }
export interface OutlineChapter { id: string; title: string; summary: string; lessons: OutlineLesson[] }
export interface CourseOutline extends Omit<CourseSummary, "chapters"> { outcomes: string[]; chapters: OutlineChapter[] }

export interface LessonRef { id: string; title: string; chapter_title: string }
export interface LessonData {
  course: { slug: string; title: string; track: string; color: string };
  lesson: {
    id: string; chapter: string; chapter_title: string; title: string; summary: string; takeaways: string[];
    kind: string; minutes: number; body: string; done: boolean; number: number; of: number;
  };
  previous: LessonRef | null;
  next: LessonRef | null;
}

export interface SearchHit { course: string; course_title: string; lesson: string; title: string; chapter_title: string; snippet: string }

export const fetchCatalog = () => request<Catalog>("/courses/hub/catalog");
export const fetchOutline = (course: string) => request<CourseOutline>(`/courses/hub/${encodeURIComponent(course)}`);
export const fetchLesson = (course: string, lesson: string) =>
  request<LessonData>(`/courses/hub/${encodeURIComponent(course)}/lessons/${encodeURIComponent(lesson)}`);
export const setLessonDone = (course: string, lesson: string, completed: boolean) =>
  request<{ course: string; lesson: string; completed: boolean }>(
    `/courses/hub/${encodeURIComponent(course)}/lessons/${encodeURIComponent(lesson)}/progress`,
    { method: "PUT", body: JSON.stringify({ completed }) });
export const searchLessons = (q: string) =>
  request<{ query: string; results: SearchHit[] }>(`/courses/hub/search?q=${encodeURIComponent(q)}`);

/** SkillDARA admin: which colleges have a licence. */
export interface LicenseRow { organization_id: string; name: string; kind: string; licensed: boolean }
export const fetchLicenses = () => request<LicenseRow[]>("/platform-admin/courses/hub/licenses");
export const setLicense = (organizationId: string, enabled: boolean) =>
  request<{ organization_id: string; licensed: boolean }>(
    `/platform-admin/courses/hub/licenses/${encodeURIComponent(organizationId)}`,
    { method: "PUT", body: JSON.stringify({ enabled }) });
