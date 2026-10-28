import { useEffect, useState } from "react";
import {
  fetchCourse, fetchCourses, mediaUrl, setLessonDone, type Course, type CourseSummary, type Lesson,
} from "../lib/courseApi";
import { embedUrl, fileSize } from "../lib/courseFormat";
import "./LearningDashboard.css";
import "./Courses.css";

function LessonPlayer({ lesson }: { lesson: Lesson }) {
  if (lesson.video_src) {
    return <video key={lesson.id} className="crs-video" controls controlsList="nodownload" preload="metadata" src={mediaUrl(lesson.video_src)} />;
  }
  const embed = lesson.video_url ? embedUrl(lesson.video_url) : null;
  if (embed) {
    return <iframe key={lesson.id} className="crs-video" src={embed} title={lesson.title} allowFullScreen
      allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" />;
  }
  return null;
}

function CourseView({ id, onBack }: { id: string; onBack: () => void }) {
  const [course, setCourse] = useState<Course | null>(null);
  const [current, setCurrent] = useState<string | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    fetchCourse(id).then((c) => {
      setCourse(c);
      setCurrent((c.lesson_list.find((l) => !l.completed) ?? c.lesson_list[0])?.id ?? null);
    }).catch((err) => setError((err as Error).message));
  }, [id]);

  const lesson = course?.lesson_list.find((l) => l.id === current) ?? null;
  const done = course?.lesson_list.filter((l) => l.completed).length ?? 0;

  async function toggle(target: Lesson) {
    try {
      await setLessonDone(target.id, !target.completed);
      setCourse((c) => c && { ...c, lesson_list: c.lesson_list.map((l) => (l.id === target.id ? { ...l, completed: !l.completed } : l)) });
    } catch (err) { setError((err as Error).message); }
  }

  return (
    <>
      <button className="hp-back" onClick={onBack}>← All courses</button>
      {error && <p className="form-error" role="alert">{error}</p>}
      {!course && !error && <div className="ld-skeleton" />}
      {course && (
        <>
          <header className="ld-head">
            <div>
              <span className="ld-kicker">{[course.category, course.level].filter(Boolean).join(" · ") || "Course"}</span>
              <h1>{course.title}</h1>
              {course.description && <p>{course.description}</p>}
            </div>
            <span className="crs-muted">{done} of {course.lesson_list.length} lessons done</span>
          </header>
          {course.lesson_list.length === 0 && <p className="ld-empty">Lessons are on their way.</p>}
          {lesson && (
            <div className="crs-layout">
              <section className="ld-card crs-main">
                <LessonPlayer lesson={lesson} />
                <h2>{lesson.title}</h2>
                {lesson.description && <p className="crs-desc">{lesson.description}</p>}
                <div className="crs-actions">
                  {lesson.notes_src && (
                    <a className="btn btn-outline btn-sm" href={mediaUrl(lesson.notes_src)} target="_blank" rel="noreferrer">
                      Open notes · {lesson.notes_name} ({fileSize(lesson.notes_size)})</a>
                  )}
                  <button type="button" className={`btn btn-sm ${lesson.completed ? "btn-outline" : "btn-primary"}`} onClick={() => void toggle(lesson)}>
                    {lesson.completed ? "Mark as not done" : "Mark as done"}</button>
                </div>
              </section>
              <nav className="ld-card crs-side" aria-label="Lessons">
                <ol>
                  {course.lesson_list.map((l) => (
                    <li key={l.id}>
                      <button type="button" className={l.id === current ? "on" : ""} onClick={() => setCurrent(l.id)}>
                        <span className={`crs-dot${l.completed ? " done" : ""}`} aria-label={l.completed ? "Done" : "Not done"}>{l.completed ? "✓" : l.position}</span>
                        <span>{l.title}<small>{[l.has_video || l.video_url ? "Video" : "", l.has_notes ? "Notes" : ""].filter(Boolean).join(" · ")}</small></span>
                      </button>
                    </li>
                  ))}
                </ol>
              </nav>
            </div>
          )}
        </>
      )}
    </>
  );
}

/** Courses SkillDARA publishes: videos and notes, with lesson progress. */
export default function Courses({ onBack }: { onBack?: () => void }) {
  const [courses, setCourses] = useState<CourseSummary[] | null>(null);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  useEffect(() => {
    if (openId) return;
    fetchCourses().then((d) => setCourses(d.courses)).catch((err) => setError((err as Error).message));
  }, [openId]);

  return (
    <div className="pv-page ld-page">
      <div className="pv-inner ld-inner">
        {openId ? <CourseView id={openId} onBack={() => setOpenId(null)} /> : (
          <>
            {onBack && <button className="hp-back" onClick={onBack}>← Back</button>}
            <header className="ld-head">
              <div>
                <span className="ld-kicker">SkillDARA</span>
                <h1>Courses</h1>
                <p>Video lessons with handbooks and notes, from the SkillDARA team.</p>
              </div>
            </header>
            {error && <p className="form-error" role="alert">{error}</p>}
            {!courses && !error && <div className="ld-skeleton" />}
            {courses && courses.length === 0 && <p className="ld-empty">No courses yet. New courses will appear here.</p>}
            {courses && courses.length > 0 && (
              <div className="crs-grid">
                {courses.map((c) => (
                  <button type="button" key={c.id} className="ld-card crs-tile" onClick={() => setOpenId(c.id)}>
                    <span className="ld-kicker">{[c.category, c.level].filter(Boolean).join(" · ") || "Course"}</span>
                    <h2>{c.title}</h2>
                    {c.description && <p>{c.description}</p>}
                    <small>{c.lessons} lessons{c.videos ? ` · ${c.videos} videos` : ""}{c.notes ? ` · ${c.notes} notes` : ""}</small>
                    {c.lessons > 0 && (
                      <div className="ld-progress" aria-label={`${c.completed} of ${c.lessons} done`}>
                        <i style={{ width: `${Math.round((c.completed / c.lessons) * 100)}%` }} />
                      </div>
                    )}
                  </button>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
