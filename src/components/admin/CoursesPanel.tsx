import { useEffect, useState, type FormEvent } from "react";
import {
  adminCourse, adminCourses, createCourse, createLesson, deleteCourse, deleteLesson, fileSize, removeLessonFile,
  updateCourse, updateLesson, uploadLessonFile, type Course, type CourseInput, type Lesson,
} from "../../lib/courseApi";
import { useLoad } from "./useLoad";
import "../Courses.css";

const EMPTY: CourseInput = { title: "", description: "", category: "", level: "", published: false };
const LEVELS = ["", "Beginner", "Intermediate", "Advanced"];

/** One lesson's editor: title, description, video (upload or link), notes. */
function LessonEditor({ courseId, lesson, chunkBytes, onChange, onDelete }: {
  courseId: string; lesson: Lesson; chunkBytes: number; onChange: (lesson: Lesson) => void; onDelete: () => void;
}) {
  const [form, setForm] = useState({ title: lesson.title, description: lesson.description, video_url: lesson.video_url ?? "" });
  const [busy, setBusy] = useState("");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const dirty = form.title !== lesson.title || form.description !== lesson.description || form.video_url !== (lesson.video_url ?? "");

  async function save() {
    setBusy("save"); setError("");
    try { onChange(await updateLesson(courseId, lesson.id, form)); } catch (err) { setError((err as Error).message); }
    setBusy("");
  }

  async function upload(kind: "video" | "notes", file: File | undefined) {
    if (!file) return;
    setBusy(kind); setProgress(0); setError("");
    try { onChange(await uploadLessonFile(lesson.id, kind, file, chunkBytes, setProgress)); } catch (err) { setError((err as Error).message); }
    setBusy("");
  }

  async function remove(kind: "video" | "notes") {
    if (!window.confirm(kind === "video" ? "Remove this lesson's video?" : "Remove this lesson's notes?")) return;
    try { onChange(await removeLessonFile(lesson.id, kind)); } catch (err) { setError((err as Error).message); }
  }

  return (
    <li className="crs-lesson-edit">
      <div className="crs-lesson-row">
        <label className="field"><span>Lesson {lesson.position}</span>
          <input value={form.title} maxLength={200} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        </label>
        <button type="button" className="btn btn-outline btn-sm" onClick={onDelete}>Delete lesson</button>
      </div>
      <label className="field"><span>What this lesson covers</span>
        <textarea rows={2} maxLength={5000} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
      </label>
      <div className="crs-files">
        <div className="crs-file">
          <b>Video</b>
          {lesson.has_video
            ? <span>{lesson.video_name} · {fileSize(lesson.video_size)} <button type="button" className="link-btn" onClick={() => void remove("video")}>Remove</button></span>
            : <span className="crs-muted">No video uploaded</span>}
          <label className="btn btn-outline btn-sm crs-pick">
            {lesson.has_video ? "Replace video" : "Upload video"}
            <input type="file" accept=".mp4,.webm,.mov,.m4v,video/*" disabled={!!busy}
              onChange={(e) => { void upload("video", e.target.files?.[0]); e.target.value = ""; }} />
          </label>
          <label className="field"><span>Or a YouTube / Vimeo link</span>
            <input value={form.video_url} maxLength={500} placeholder="https://www.youtube.com/watch?v=…"
              onChange={(e) => setForm({ ...form, video_url: e.target.value })} />
          </label>
        </div>
        <div className="crs-file">
          <b>Handbook or notes</b>
          {lesson.has_notes
            ? <span>{lesson.notes_name} · {fileSize(lesson.notes_size)} <button type="button" className="link-btn" onClick={() => void remove("notes")}>Remove</button></span>
            : <span className="crs-muted">PDF, Word, PowerPoint or text, up to 100 MB</span>}
          <label className="btn btn-outline btn-sm crs-pick">
            {lesson.has_notes ? "Replace notes" : "Upload notes"}
            <input type="file" accept=".pdf,.docx,.pptx,.txt" disabled={!!busy}
              onChange={(e) => { void upload("notes", e.target.files?.[0]); e.target.value = ""; }} />
          </label>
        </div>
      </div>
      {(busy === "video" || busy === "notes") && (
        <div className="crs-upload" role="status">
          <div className="crs-bar"><i style={{ width: `${Math.round(progress * 100)}%` }} /></div>
          <span>Uploading {busy}… {Math.round(progress * 100)}%. Keep this page open.</span>
        </div>
      )}
      {error && <p className="form-error" role="alert">{error}</p>}
      {dirty && <button type="button" className="btn btn-primary btn-sm" disabled={!!busy} onClick={() => void save()}>
        {busy === "save" ? "Saving…" : "Save lesson"}</button>}
    </li>
  );
}

/** SkillDARA admin: create courses, add lessons, upload videos and notes, publish. */
export default function CoursesPanel() {
  const { data, error, loading, reload } = useLoad(() => adminCourses(), []);
  const [openId, setOpenId] = useState<string | null>(null);
  const [course, setCourse] = useState<Course | null>(null);
  const [form, setForm] = useState<CourseInput>(EMPTY);
  const [lessonTitle, setLessonTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const chunkBytes = data?.chunk_bytes ?? 8 * 1024 * 1024;

  useEffect(() => {
    setMessage("");
    if (!openId || openId === "new") { setCourse(null); setForm(EMPTY); return; }
    adminCourse(openId).then((c) => {
      setCourse(c);
      setForm({ title: c.title, description: c.description, category: c.category, level: c.level, published: c.published });
    }).catch((err) => setMessage((err as Error).message));
  }, [openId]);

  async function saveCourse(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setMessage("");
    try {
      const saved = course ? await updateCourse(course.id, form) : await createCourse(form);
      setCourse(saved); setOpenId(saved.id); reload();
      setMessage(saved.published ? "Saved. Learners can see this course." : "Saved as a draft. Learners cannot see it yet.");
    } catch (err) { setMessage((err as Error).message); }
    setBusy(false);
  }

  async function addLesson(event: FormEvent) {
    event.preventDefault();
    if (!course || lessonTitle.trim().length < 2) return;
    try {
      const lesson = await createLesson(course.id, { title: lessonTitle.trim(), description: "", video_url: "" });
      setCourse({ ...course, lesson_list: [...course.lesson_list, lesson] });
      setLessonTitle(""); reload();
    } catch (err) { setMessage((err as Error).message); }
  }

  async function removeCourse() {
    if (!course || !window.confirm(`Delete "${course.title}" with all its lessons, videos and notes?`)) return;
    try { await deleteCourse(course.id); setOpenId(null); reload(); } catch (err) { setMessage((err as Error).message); }
  }

  async function removeLesson(lesson: Lesson) {
    if (!course || !window.confirm(`Delete the lesson "${lesson.title}" and its files?`)) return;
    try {
      await deleteLesson(lesson.id);
      setCourse({ ...course, lesson_list: course.lesson_list.filter((l) => l.id !== lesson.id) }); reload();
    } catch (err) { setMessage((err as Error).message); }
  }

  if (!openId) {
    return (
      <div className="admin-section">
        {error && <div className="admin-error">{error} <button className="btn btn-outline btn-sm" onClick={reload}>Retry</button></div>}
        <div className="crs-toolbar">
          <p className="crs-muted">Courses you publish appear under Courses in every learner's sidebar.</p>
          <button type="button" className="btn btn-primary btn-sm" onClick={() => setOpenId("new")}>New course</button>
        </div>
        <div className="admin-table-card">
          <table className="admin-table">
            <thead><tr><th>Course</th><th>Lessons</th><th>Videos</th><th>Notes</th><th>Status</th><th /></tr></thead>
            <tbody>
              {data?.courses.map((c) => (
                <tr key={c.id}>
                  <td className="admin-table-primary">{c.title}<br /><small>{[c.category, c.level].filter(Boolean).join(" · ")}</small></td>
                  <td>{c.lessons}</td><td>{c.videos}</td><td>{c.notes}</td>
                  <td><span className={`admin-badge ${c.published ? "badge-active" : "badge-pending"}`}>{c.published ? "Published" : "Draft"}</span></td>
                  <td><button type="button" className="btn btn-outline btn-sm" onClick={() => setOpenId(c.id)}>Edit</button></td>
                </tr>
              ))}
              {data && !data.courses.length && <tr><td colSpan={6} className="admin-table-empty">No courses yet. Create the first one.</td></tr>}
              {loading && !data && <tr><td colSpan={6} className="admin-table-empty">Loading…</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-section crs-admin">
      <button type="button" className="hp-back" onClick={() => setOpenId(null)}>← All courses</button>
      <form className="crs-card" onSubmit={saveCourse}>
        <h3>{course ? "Course details" : "New course"}</h3>
        <label className="field"><span>Title</span>
          <input required minLength={3} maxLength={200} value={form.title} placeholder="e.g. Python for beginners"
            onChange={(e) => setForm({ ...form, title: e.target.value })} />
        </label>
        <label className="field"><span>Description</span>
          <textarea rows={3} maxLength={5000} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        </label>
        <div className="crs-two">
          <label className="field"><span>Category</span>
            <input maxLength={80} value={form.category} placeholder="e.g. Programming" onChange={(e) => setForm({ ...form, category: e.target.value })} />
          </label>
          <label className="field"><span>Level</span>
            <select value={form.level} onChange={(e) => setForm({ ...form, level: e.target.value })}>
              {LEVELS.map((l) => <option key={l} value={l}>{l || "Any level"}</option>)}
            </select>
          </label>
        </div>
        <label className="crs-check">
          <input type="checkbox" checked={form.published} onChange={(e) => setForm({ ...form, published: e.target.checked })} />
          Published (learners can see it)
        </label>
        {message && <p className="crs-muted" role="status">{message}</p>}
        <div className="crs-actions">
          <button className="btn btn-primary btn-sm" disabled={busy}>{busy ? "Saving…" : course ? "Save course" : "Create course"}</button>
          {course && <button type="button" className="btn btn-outline btn-sm" onClick={() => void removeCourse()}>Delete course</button>}
        </div>
      </form>

      {course && (
        <section className="crs-card">
          <h3>Lessons</h3>
          <ol className="crs-lesson-list">
            {course.lesson_list.map((lesson) => (
              <LessonEditor key={lesson.id} courseId={course.id} lesson={lesson} chunkBytes={chunkBytes}
                onChange={(next) => { setCourse((c) => c && { ...c, lesson_list: c.lesson_list.map((l) => (l.id === next.id ? next : l)) }); reload(); }}
                onDelete={() => void removeLesson(lesson)} />
            ))}
          </ol>
          <form className="crs-add" onSubmit={addLesson}>
            <input value={lessonTitle} maxLength={200} placeholder="New lesson title" onChange={(e) => setLessonTitle(e.target.value)} />
            <button className="btn btn-outline btn-sm" disabled={lessonTitle.trim().length < 2}>Add lesson</button>
          </form>
        </section>
      )}
    </div>
  );
}
