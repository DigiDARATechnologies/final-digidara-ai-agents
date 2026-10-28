/** Courses (orchestrator app/courses): SkillDARA's admin publishes, everyone learns. */
import { sessionToken } from "./session";

const RAW_BASE = import.meta.env.VITE_GATEWAY_API_URL !== undefined ? import.meta.env.VITE_GATEWAY_API_URL : "http://127.0.0.1:8100";
const BASE = RAW_BASE.endsWith("/") ? RAW_BASE.slice(0, -1) : RAW_BASE;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${sessionToken() || ""}`, ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : Array.isArray(body.detail) ? body.detail[0]?.msg : null;
    throw new Error(detail || "Something went wrong. Please try again.");
  }
  return response.json();
}

const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });

export interface Lesson {
  id: string;
  title: string;
  description: string;
  position: number;
  video_url: string | null;
  has_video: boolean;
  video_name: string;
  video_size: number;
  video_src?: string;
  has_notes: boolean;
  notes_name: string;
  notes_size: number;
  notes_src?: string;
  completed: boolean;
}

export interface CourseSummary {
  id: string;
  title: string;
  description: string;
  category: string;
  level: string;
  published: boolean;
  position: number;
  lessons: number;
  completed: number;
  videos: number;
  notes: number;
  updated_at: string | null;
}

export interface Course extends CourseSummary {
  lesson_list: Lesson[];
}

export interface CourseInput {
  title: string;
  description: string;
  category: string;
  level: string;
  published: boolean;
}

export interface LessonInput {
  title: string;
  description: string;
  video_url: string;
}

/** A signed media path from the API, as a full URL for <video>, <a> or <iframe>. */
export const mediaUrl = (src: string) => `${BASE}${src}`;

export { embedUrl, fileSize } from "./courseFormat";

// --- learners ---
export const fetchCourses = () => request<{ courses: CourseSummary[] }>("/courses");
export const fetchCourse = (id: string) => request<Course>(`/courses/${id}`);
export const setLessonDone = (lessonId: string, completed: boolean) =>
  request<{ lesson_id: string; completed: boolean }>(`/courses/lessons/${lessonId}/progress`, json("PUT", { completed }));

// --- SkillDARA admin ---
export const adminCourses = () => request<{ courses: CourseSummary[]; chunk_bytes: number }>("/platform-admin/courses");
export const adminCourse = (id: string) => request<Course>(`/platform-admin/courses/${id}`);
export const createCourse = (body: CourseInput) => request<Course>("/platform-admin/courses", json("POST", body));
export const updateCourse = (id: string, body: CourseInput) => request<Course>(`/platform-admin/courses/${id}`, json("PUT", body));
export const deleteCourse = (id: string) => request<{ deleted: string }>(`/platform-admin/courses/${id}`, { method: "DELETE" });
export const createLesson = (courseId: string, body: LessonInput) =>
  request<Lesson>(`/platform-admin/courses/${courseId}/lessons`, json("POST", body));
export const updateLesson = (courseId: string, lessonId: string, body: LessonInput) =>
  request<Lesson>(`/platform-admin/courses/${courseId}/lessons/${lessonId}`, json("PUT", body));
export const deleteLesson = (lessonId: string) =>
  request<{ deleted: string }>(`/platform-admin/courses/lessons/${lessonId}`, { method: "DELETE" });
export const removeLessonFile = (lessonId: string, kind: "video" | "notes") =>
  request<Lesson>(`/platform-admin/courses/lessons/${lessonId}/${kind}`, { method: "DELETE" });

function uploadId(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

/** Sends a file in chunks (so big videos pass any upload limit); reports progress 0..1. */
export async function uploadLessonFile(
  lessonId: string, kind: "video" | "notes", file: File, chunkBytes: number, onProgress?: (fraction: number) => void,
): Promise<Lesson> {
  const id = uploadId();
  const total = Math.max(1, Math.ceil(file.size / chunkBytes));
  let lesson: Lesson | undefined;
  for (let index = 0; index < total; index += 1) {
    const params = new URLSearchParams({ kind, upload_id: id, index: String(index), total: String(total), filename: file.name });
    const body = file.slice(index * chunkBytes, (index + 1) * chunkBytes);
    let result: { done: boolean; lesson?: Lesson } | undefined;
    for (let attempt = 0; attempt < 3 && !result; attempt += 1) {
      try {
        result = await request(`/platform-admin/courses/lessons/${lessonId}/upload?${params}`, {
          method: "PUT", body, headers: { "Content-Type": "application/octet-stream" },
        });
      } catch (err) {
        if (attempt === 2 || /use |up to|No such/.test((err as Error).message)) throw err;
      }
    }
    onProgress?.((index + 1) / total);
    if (result?.done) lesson = result.lesson;
  }
  if (!lesson) throw new Error("The upload did not finish. Please try again.");
  return lesson;
}
