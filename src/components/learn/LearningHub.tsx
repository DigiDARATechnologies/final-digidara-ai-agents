import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchCatalog, fetchLesson, fetchOutline, LearnApiError, searchLessons, setLessonDone,
  type Catalog, type CourseOutline, type CourseSummary, type LessonData, type SearchHit,
} from "../../lib/learnApi";
import { outlineOf, parseBlocks } from "../../lib/learnMarkdown";
import LessonBody from "./LessonBody";
import "./Learn.css";

export interface LearningHubProps {
  /** Opens an agent chat (Practise this). */
  onOpenAgent?: (agentId: string) => void;
  /** Opens the coin purchase screen. */
  onBuyCoins?: () => void;
}

type Route = { view: "home" } | { view: "track"; track: string } | { view: "course"; course: string } | { view: "lesson"; course: string; lesson: string };

/** A small mark for each category. The whole hub uses one calm accent colour, so only the glyph differs. */
const GLYPHS: Record<string, string> = {
  technical: "{ }", "data-ai": "∑", aptitude: "%", interview: "Q&A", communication: "Aa", projects: "★",
};
const glyphOf = (id: string) => GLYPHS[id] ?? "•";
const TINTS: Record<string, string> = {
  technical: "#2f4fd0", "data-ai": "#0d9488", aptitude: "#ea580c", interview: "#9333ea", communication: "#0284c7", projects: "#7c3aed",
};
const tintOf = (id: string) => TINTS[id] ?? "#475569";
const levelKey = (level: string) => (level.toLowerCase().startsWith("adv") ? "a" : level.toLowerCase().startsWith("int") ? "i" : "b");
const percentOf = (done: number, total: number) => (total ? Math.round((done / total) * 100) : 0);

const hhmm = (minutes: number) => (minutes >= 60 ? `${Math.floor(minutes / 60)} h ${minutes % 60 ? `${minutes % 60} min` : ""}`.trim() : `${minutes} min`);

function LockedPage({ reason, onBuyCoins }: { reason: string; onBuyCoins?: () => void }) {
  const over = reason === "no_coins";
  return (
    <section className="lh-locked" aria-label="Learning Hub is locked">
      <div className="lh-lock-icon" aria-hidden="true">🔒</div>
      <h2>{over ? "Your coins are over" : "The Learning Hub opens with coins"}</h2>
      <p>
        {over
          ? "Buy coins to keep reading. Your progress is saved and waiting for you."
          : "Tutorials, aptitude, interview, communication and project lessons are for learners who have bought coins. Your college can also unlock it for you."}
      </p>
      {onBuyCoins && <button type="button" className="btn btn-primary" onClick={onBuyCoins}>Buy coins</button>}
      <ul className="lh-lock-list">
        <li>Step-by-step tutorials with code you can copy</li>
        <li>Aptitude topics with worked examples</li>
        <li>Interview questions with answers you can say aloud</li>
      </ul>
    </section>
  );
}

function CourseCard({ course, onOpen }: { course: CourseSummary; onOpen: (slug: string) => void }) {
  const percent = percentOf(course.completed, course.lessons);
  const unit = course.kind === "qa" ? "question sets" : "lessons";
  return (
    <button type="button" className="lh-card" style={{ ["--cc" as string]: course.color }} onClick={() => onOpen(course.slug)}
      aria-label={`${course.title}, ${course.lessons} ${unit}`}>
      <span className="lh-card-top">
        <span className="lh-card-icon" aria-hidden="true">{course.icon || course.title.slice(0, 2)}</span>
        <span className={`lh-chip lv-${levelKey(course.level)}`}>{course.level}</span>
      </span>
      <span className="lh-card-body">
        <b>{course.title}</b>
        <small>{course.summary}</small>
      </span>
      <span className="lh-card-meta"><span>{course.lessons} {unit}</span><span>{hhmm(course.minutes)}</span></span>
      <span className="lh-card-prog">
        <span className="lh-card-prog-row"><em>Progress</em><b>{percent}%</b></span>
        <span className="lh-bar" role="img" aria-label={`${percent}% done`}><i style={{ width: `${percent}%` }} /></span>
      </span>
      <span className="lh-card-btn">{course.completed > 0 ? "Continue learning" : "Start learning"}</span>
    </button>
  );
}

function Crumbs({ items }: { items: { label: string; onClick?: () => void }[] }) {
  return (
    <nav className="lh-trail" aria-label="Breadcrumb">
      {items.map((item, i) => (
        <span key={`${item.label}-${i}`}>
          {item.onClick ? <button type="button" onClick={item.onClick}>{item.label}</button> : <b aria-current="page">{item.label}</b>}
          {i < items.length - 1 && <i aria-hidden="true">›</i>}
        </span>
      ))}
    </nav>
  );
}

const liveOf = (courses: CourseSummary[]) => courses.filter((c) => c.status === "live");
const lessonsOf = (courses: CourseSummary[]) => liveOf(courses).reduce((n, c) => n + c.lessons, 0);

/** The category tabs: the same bar on the home page and on every category page, so moving between categories is one click. */
function TrackSwitch({ catalog, current, onOpen, onHome }: { catalog: Catalog; current: string; onOpen: (id: string) => void; onHome: () => void }) {
  return (
    <nav className="lh-switcher" aria-label="Categories">
      <button type="button" className={current === "home" ? "on" : ""} aria-current={current === "home" ? "page" : undefined} onClick={onHome}>Overview</button>
      {catalog.tracks.map((t) => (
        <button key={t.id} type="button" className={t.id === current ? "on" : ""} aria-current={t.id === current ? "page" : undefined} onClick={() => onOpen(t.id)}>
          {t.title}
        </button>
      ))}
    </nav>
  );
}

function Home({ catalog, onOpen, onOpenTrack, onSearch }: {
  catalog: Catalog; onOpen: (slug: string) => void; onOpenTrack: (id: string) => void; onSearch: (slug: string, lesson: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [error, setError] = useState("");
  const latest = useRef(0);
  const all = catalog.tracks.flatMap((t) => t.courses);
  const started = all.filter((c) => c.status === "live" && c.completed > 0 && c.completed < c.lessons);
  const lastStarted = started[0];
  const resume = lastStarted ?? all.find((c) => c.slug === "python" && c.status === "live") ?? liveOf(all)[0];

  useEffect(() => {
    const text = query.trim();
    if (text.length < 2) { setHits(null); return; }
    const ticket = ++latest.current;
    const timer = window.setTimeout(() => {
      searchLessons(text).then((r) => { if (ticket === latest.current) { setHits(r.results); setError(""); } })
        .catch((err) => { if (ticket === latest.current) setError((err as Error).message); });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  return (
    <>
      <header className="lh-top">
        <div className="lh-top-text">
          <h1>Learning Hub</h1>
          <p>Tutorials, aptitude, interview answers, communication skills and hands-on projects, written for placements and first jobs.</p>
        </div>
        <label className="lh-search">
          <span className="lh-sr">Search lessons</span>
          <input type="search" value={query} placeholder="Search lessons, e.g. joins or percentages" onChange={(e) => setQuery(e.target.value)} />
        </label>
      </header>
      <TrackSwitch catalog={catalog} current="home" onOpen={onOpenTrack} onHome={() => setQuery("")} />

      {error && <p className="form-error" role="alert">{error}</p>}
      {hits && (
        <section className="lh-results" aria-label="Search results">
          <h2>{hits.length ? `${hits.length} result${hits.length === 1 ? "" : "s"}` : "No lessons match"}</h2>
          {hits.map((h) => (
            <button type="button" key={`${h.course}/${h.lesson}`} onClick={() => onSearch(h.course, h.lesson)}>
              <b>{h.title}</b><small>{h.course_title} · {h.chapter_title}</small>{h.snippet && <span>{h.snippet}…</span>}
            </button>
          ))}
        </section>
      )}

      {!hits && (
        <>
          {resume && (
            <section className="lh-banner" aria-label={lastStarted ? "Continue learning" : "Start here"}>
              <div>
                <span className="lh-eyebrow">{lastStarted ? "Continue learning" : "Start here"}</span>
                <h2>{resume.title}</h2>
                <p>{resume.summary}</p>
              </div>
              <div className="lh-banner-side">
                {lastStarted && (
                  <div className="lh-banner-pct"><b>{percentOf(resume.completed, resume.lessons)}%</b><small>{resume.completed} of {resume.lessons} lessons</small></div>
                )}
                <button type="button" className="lh-btn" onClick={() => onOpen(resume.slug)}>{lastStarted ? "Continue" : "Start learning"} →</button>
              </div>
            </section>
          )}

          {started.length > 1 && (
            <section className="lh-section">
              <div className="lh-section-head"><span className="lh-eyebrow">In progress</span><h2>Pick up where you left off</h2></div>
              <div className="lh-grid">{started.slice(1).map((c) => <CourseCard key={c.slug} course={c} onOpen={onOpen} />)}</div>
            </section>
          )}

          <section className="lh-section">
            <div className="lh-section-head"><span className="lh-eyebrow">Categories</span><h2>Browse by category</h2><p>Pick a category to see its courses.</p></div>
            <div className="lh-cats">
              {catalog.tracks.map((t) => {
                const live = liveOf(t.courses);
                const lessons = lessonsOf(t.courses);
                const done = live.reduce((n, c) => n + c.completed, 0);
                const percent = percentOf(done, lessons);
                const names = (live.length ? live : t.courses).map((c) => c.title);
                const more = names.length > 3 ? ` +${names.length - 3} more` : "";
                return (
                  <button key={t.id} type="button" className="lh-cat" style={{ ["--t" as string]: tintOf(t.id) }} onClick={() => onOpenTrack(t.id)}
                    aria-label={`${t.title}: ${live.length} courses, ${lessons} lessons`}>
                    <span className="lh-cat-top">
                      <span className="lh-cat-icon" aria-hidden="true">{glyphOf(t.id)}</span>
                      <span className="lh-cat-name"><b>{t.title}</b><small>{t.blurb}</small></span>
                    </span>
                    {live.length > 0 ? (
                      <span className="lh-chips"><span className="lh-chip c1">{live.length} course{live.length === 1 ? "" : "s"}</span><span className="lh-chip c2">{lessons} lessons</span></span>
                    ) : (
                      <span className="lh-chips"><span className="lh-chip c3">Coming soon</span></span>
                    )}
                    <span className="lh-cat-list">{names.slice(0, 3).join(" · ")}{more}</span>
                    <span className="lh-card-prog">
                      <span className="lh-card-prog-row"><em>Progress</em><b>{percent}%</b></span>
                      <span className="lh-bar" role="img" aria-label={`${percent}% done`}><i style={{ width: `${percent}%` }} /></span>
                    </span>
                    <span className="lh-card-btn">Explore {t.title}</span>
                  </button>
                );
              })}
            </div>
          </section>

          {catalog.paths.length > 0 && (
            <section className="lh-section">
              <div className="lh-section-head"><span className="lh-eyebrow">Learning paths</span><h2>Guided learning paths</h2><p>Not sure where to start? Follow a path, one course after another.</p></div>
              <div className="lh-paths">
                {catalog.paths.map((p) => (
                  <article key={p.id} className="lh-path">
                    <h3>{p.title}</h3>
                    <p>{p.summary}</p>
                    <ol>
                      {p.courses.map((c) => (
                        <li key={c.slug}>
                          {c.status === "live"
                            ? <button type="button" onClick={() => onOpen(c.slug)}>{c.title}</button>
                            : <span>{c.title} <em>soon</em></span>}
                        </li>
                      ))}
                    </ol>
                  </article>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </>
  );
}

function TrackPage({ catalog, trackId, onOpenTrack, onOpen, onHome }: {
  catalog: Catalog; trackId: string; onOpenTrack: (id: string) => void; onOpen: (slug: string) => void; onHome: () => void;
}) {
  const track = catalog.tracks.find((t) => t.id === trackId) ?? catalog.tracks[0];
  const live = liveOf(track.courses);
  const soon = track.courses.filter((c) => c.status !== "live");
  const done = live.reduce((n, c) => n + c.completed, 0);
  return (
    <>
      <Crumbs items={[{ label: "Learning Hub", onClick: onHome }, { label: track.title }]} />
      <TrackSwitch catalog={catalog} current={track.id} onOpen={onOpenTrack} onHome={onHome} />
      <header className="lh-banner lh-track-banner" style={{ ["--t" as string]: tintOf(track.id) }}>
        <span className="lh-cat-icon big" aria-hidden="true">{glyphOf(track.id)}</span>
        <div>
          <h1>{track.title}</h1>
          <p>{track.blurb}</p>
          <ul className="lh-facts">
            <li><b>{live.length}</b> courses</li>
            <li><b>{lessonsOf(track.courses)}</b> lessons</li>
            {done > 0 && <li><b>{done}</b> completed</li>}
          </ul>
        </div>
      </header>

      {live.length > 0 && (
        <section className="lh-section">
          <div className="lh-section-head"><span className="lh-eyebrow">{track.title}</span><h2>Courses</h2></div>
          <div className="lh-grid">{live.map((c) => <CourseCard key={c.slug} course={c} onOpen={onOpen} />)}</div>
        </section>
      )}
      {live.length === 0 && <p className="lh-empty">The first courses in {track.title} are being written. Pick another category while you wait.</p>}
      {soon.length > 0 && (
        <section className="lh-section">
          <div className="lh-section-head"><span className="lh-eyebrow">Planned</span><h2>Coming soon</h2></div>
          <ul className="lh-soon">{soon.map((c) => <li key={c.slug}><span aria-hidden="true">{c.icon}</span>{c.title}</li>)}</ul>
        </section>
      )}
    </>
  );
}

function CoursePage({ course, trackTitle, onHome, onBack, onOpenLesson }: { course: CourseOutline; trackTitle: string; onHome: () => void; onBack: () => void; onOpenLesson: (lesson: string) => void }) {
  const lessons = course.chapters.flatMap((c) => c.lessons);
  const next = lessons.find((l) => !l.done) ?? lessons[0];
  const percent = course.lessons ? Math.round((course.completed / course.lessons) * 100) : 0;
  return (
    <>
      <Crumbs items={[{ label: "Learning Hub", onClick: onHome }, { label: trackTitle, onClick: onBack }, { label: course.title }]} />
      <header className="lh-course-head">
        <div>
          <span className="lh-label">{course.level} · {course.kind === "qa" ? "Interview questions" : "Tutorial"}</span>
          <h1>{course.title}</h1>
          <p>{course.summary}</p>
          <ul className="lh-facts">
            <li><b>{course.lessons}</b> {course.kind === "qa" ? "question sets" : "lessons"}</li>
            <li><b>{course.chapters.length}</b> chapters</li>
            <li><b>{hhmm(course.minutes)}</b> to read</li>
          </ul>
          {next && (
            <button type="button" className="btn btn-primary" onClick={() => onOpenLesson(next.id)}>
              {course.completed ? "Continue" : "Start learning"} →
            </button>
          )}
        </div>
        <div className="lh-ring" role="img" aria-label={`${percent}% done`}>
          <svg viewBox="0 0 36 36"><circle cx="18" cy="18" r="15.9" className="t" /><circle cx="18" cy="18" r="15.9" className="v" strokeDasharray={`${percent} 100`} /></svg>
          <span><b>{percent}%</b><small>{course.completed} of {course.lessons}</small></span>
        </div>
      </header>
      {course.outcomes.length > 0 && (
        <section className="lh-outcomes">
          <h2>What you will be able to do</h2>
          <ul>{course.outcomes.map((o) => <li key={o}>{o}</li>)}</ul>
        </section>
      )}
      <section className="lh-chapters">
        <h2>Contents</h2>
        {course.chapters.map((chapter, n) => (
          <article key={chapter.id} className="lh-chapter">
            <header><span>{n + 1}</span><div><b>{chapter.title}</b>{chapter.summary && <small>{chapter.summary}</small>}</div></header>
            <ol>
              {chapter.lessons.map((l) => (
                <li key={l.id}>
                  <button type="button" onClick={() => onOpenLesson(l.id)} className={l.done ? "done" : ""}>
                    <i aria-hidden="true">{l.done ? "✓" : ""}</i><span>{l.title}</span><small>{l.minutes} min</small>
                  </button>
                </li>
              ))}
            </ol>
          </article>
        ))}
      </section>
    </>
  );
}

function Reader({ course, data, onNavigate, onBack, onToggle, onOpenAgent }: {
  course: CourseOutline; data: LessonData; onNavigate: (lesson: string) => void; onBack: () => void;
  onToggle: (done: boolean) => void; onOpenAgent?: (id: string) => void;
}) {
  const { lesson } = data;
  const [railOpen, setRailOpen] = useState(false);
  const toc = useMemo(() => (lesson.kind === "qa" ? [] : outlineOf(parseBlocks(lesson.body))), [lesson.body, lesson.kind]);
  const percent = course.lessons ? Math.round((course.completed / course.lessons) * 100) : 0;
  const top = useRef<HTMLDivElement>(null);
  useEffect(() => { top.current?.scrollIntoView({ block: "start" }); }, [lesson.id]);

  return (
    <div className="lh-reader">
      <aside className={`lh-rail${railOpen ? " open" : ""}`} aria-label="Course contents">
        <button type="button" className="lh-rail-title" onClick={onBack}>← {course.title}</button>
        <div className="lh-rail-progress" role="img" aria-label={`${percent}% done`}><i style={{ width: `${percent}%` }} /></div>
        <small className="lh-rail-count">{course.completed} of {course.lessons} done</small>
        <nav>
          {course.chapters.map((chapter) => (
            <div key={chapter.id} className="lh-rail-chapter">
              <b>{chapter.title}</b>
              {chapter.lessons.map((l) => (
                <button key={l.id} type="button" className={`${l.id === lesson.id ? "on" : ""}${l.done ? " done" : ""}`}
                  aria-current={l.id === lesson.id ? "page" : undefined} onClick={() => { setRailOpen(false); onNavigate(l.id); }}>
                  <i aria-hidden="true">{l.done ? "✓" : ""}</i>{l.title}
                </button>
              ))}
            </div>
          ))}
        </nav>
      </aside>

      <article className="lh-article">
        <div ref={top} />
        <button type="button" className="lh-rail-toggle" aria-expanded={railOpen} onClick={() => setRailOpen((v) => !v)}>
          ☰ Contents
        </button>
        <nav className="lh-crumbs" aria-label="Breadcrumb">
          <button type="button" onClick={onBack}>{data.course.title}</button><span>›</span><span>{lesson.chapter_title}</span>
        </nav>
        <header className="lh-lesson-head">
          <small>Lesson {lesson.number} of {lesson.of} · {lesson.minutes} min read</small>
          <h1>{lesson.title}</h1>
          {lesson.summary && <p>{lesson.summary}</p>}
        </header>
        {lesson.takeaways.length > 0 && (
          <section className="lh-takeaways" aria-label="In this lesson">
            <b>In this lesson</b>
            <ul>{lesson.takeaways.map((t) => <li key={t}>{t}</li>)}</ul>
          </section>
        )}
        <LessonBody body={lesson.body} kind={lesson.kind} onOpenAgent={onOpenAgent} />
        <footer className="lh-lesson-foot">
          <button type="button" className={`btn ${lesson.done ? "btn-outline" : "btn-primary"}`} onClick={() => onToggle(!lesson.done)}>
            {lesson.done ? "✓ Completed (undo)" : "Mark as complete"}
          </button>
          <div className="lh-prevnext">
            {data.previous && <button type="button" onClick={() => onNavigate(data.previous!.id)}><small>← Previous</small><b>{data.previous.title}</b></button>}
            {data.next && <button type="button" className="next" onClick={() => onNavigate(data.next!.id)}><small>Next →</small><b>{data.next.title}</b></button>}
          </div>
        </footer>
      </article>

      {toc.length > 1 && (
        <aside className="lh-toc" aria-label="On this page">
          <b>On this page</b>
          {toc.map((h) => <a key={h.id} href={`#${h.id}`} onClick={(e) => { e.preventDefault(); document.getElementById(h.id)?.scrollIntoView({ behavior: "smooth", block: "start" }); }}>{h.text}</a>)}
        </aside>
      )}
    </div>
  );
}

export default function LearningHub({ onOpenAgent, onBuyCoins }: LearningHubProps) {
  const [route, setRoute] = useState<Route>({ view: "home" });
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [outline, setOutline] = useState<CourseOutline | null>(null);
  const [lesson, setLesson] = useState<LessonData | null>(null);
  const [error, setError] = useState("");
  const [lockedReason, setLockedReason] = useState("");

  const fail = useCallback((err: unknown) => {
    if (err instanceof LearnApiError && err.status === 402) setLockedReason(/over/i.test(err.message) ? "no_coins" : "no_purchase");
    else setError((err as Error).message);
  }, []);

  useEffect(() => {
    if (route.view !== "home" && route.view !== "track") return;
    fetchCatalog().then((c) => { setCatalog(c); setLockedReason(c.access.unlocked ? "" : c.access.reason); setError(""); }).catch(fail);
  }, [route.view, fail]);

  const courseSlug = route.view === "course" || route.view === "lesson" ? route.course : null;
  useEffect(() => {
    if (!courseSlug) { setOutline(null); return; }
    fetchOutline(courseSlug).then((o) => { setOutline(o); setError(""); }).catch(fail);
  }, [courseSlug, fail]);

  const lessonId = route.view === "lesson" ? route.lesson : null;
  useEffect(() => {
    if (!courseSlug || !lessonId) { setLesson(null); return; }
    fetchLesson(courseSlug, lessonId).then((l) => { setLesson(l); setError(""); }).catch(fail);
  }, [courseSlug, lessonId, fail]);

  async function toggleDone(done: boolean) {
    if (!lesson) return;
    try {
      await setLessonDone(lesson.course.slug, lesson.lesson.id, done);
      setLesson({ ...lesson, lesson: { ...lesson.lesson, done } });
      setOutline((o) => o && {
        ...o, completed: o.completed + (done ? 1 : -1),
        chapters: o.chapters.map((c) => ({ ...c, lessons: c.lessons.map((l) => (l.id === lesson.lesson.id ? { ...l, done } : l)) })),
      });
    } catch (err) { fail(err); }
  }

  if (lockedReason) return <LockedPage reason={lockedReason} onBuyCoins={onBuyCoins} />;
  if (error) return <p className="form-error" role="alert">{error}</p>;

  if (route.view === "lesson") {
    if (!outline || !lesson || lesson.lesson.id !== route.lesson) return <div className="lh-loading" aria-busy="true" />;
    return <Reader course={outline} data={lesson} onBack={() => setRoute({ view: "course", course: route.course })}
      onNavigate={(l) => setRoute({ view: "lesson", course: route.course, lesson: l })} onToggle={(d) => void toggleDone(d)} onOpenAgent={onOpenAgent} />;
  }
  if (route.view === "course") {
    if (!outline) return <div className="lh-loading" aria-busy="true" />;
    const trackTitle = catalog?.tracks.find((t) => t.id === outline.track)?.title ?? "Courses";
    return <CoursePage course={outline} trackTitle={trackTitle} onHome={() => setRoute({ view: "home" })}
      onBack={() => setRoute({ view: "track", track: outline.track })} onOpenLesson={(l) => setRoute({ view: "lesson", course: route.course, lesson: l })} />;
  }
  if (!catalog) return <div className="lh-loading" aria-busy="true" />;
  const openCourse = (slug: string) => setRoute({ view: "course", course: slug });
  if (route.view === "track") {
    return <TrackPage catalog={catalog} trackId={route.track} onOpenTrack={(id) => setRoute({ view: "track", track: id })} onOpen={openCourse} onHome={() => setRoute({ view: "home" })} />;
  }
  return <Home catalog={catalog} onOpen={openCourse} onOpenTrack={(id) => setRoute({ view: "track", track: id })} onSearch={(slug, l) => setRoute({ view: "lesson", course: slug, lesson: l })} />;
}
