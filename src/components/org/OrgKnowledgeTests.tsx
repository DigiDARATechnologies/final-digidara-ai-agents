import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import {
  createKnowledgeTest, deleteKnowledgeDocument, deleteKnowledgeQuestion, deleteKnowledgeTest, fetchKnowledgeTest,
  fetchKnowledgeTests, generateKnowledgeQuestions, QUESTION_TYPE_LABELS, updateKnowledgeQuestion, updateKnowledgeTest,
  uploadKnowledgeDocument, type KnowledgeQuestion, type KnowledgeTest, type QuestionType, type UploadResult,
} from "../../lib/knowledgeApi";
import { formatWhen } from "../../lib/proctoring";
import "../Knowledge.css";
import "../Proctor.css";

const ACCEPT = ".pdf,.docx,.pptx,.txt,.md,.csv,.png,.jpg,.jpeg,.webp";
const LETTERS = ["A", "B", "C", "D"];
const STATUS_TEXT: Record<KnowledgeTest["status"], string> = {
  draft: "Draft", generating: "Writing questions…", ready: "Ready", failed: "Needs attention",
};

interface Props {
  orgId: string;
  onToast: (message: string) => void;
  /** Share a ready test: opens the Assessments tab with it chosen. */
  onCreateLink: (testId: string) => void;
}

function CreateTest({ orgId, onCreated, onToast }: { orgId: string; onCreated: (test: KnowledgeTest) => void; onToast: (m: string) => void }) {
  const [title, setTitle] = useState("");
  const [type, setType] = useState<QuestionType>("mcq");
  const [count, setCount] = useState(10);
  const [seconds, setSeconds] = useState(90);
  const [instructions, setInstructions] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const test = await createKnowledgeTest(orgId, { title, question_type: type, num_questions: count, seconds_per_question: seconds, instructions });
      setTitle("");
      setInstructions("");
      onCreated(test);
    } catch (err) {
      onToast((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="org-card">
      <h3>Create a knowledge test</h3>
      <p className="rd-muted">Upload your own material (notes, slides, PDFs, photos of pages). The AI writes the questions and answers
        from it only. You check them, then share the test as an assessment link. Only admins can see the answers.</p>
      <form className="assess-form" onSubmit={submit}>
        <label>Title
          <input type="text" value={title} required minLength={3} maxLength={200} placeholder="e.g. Python basics – unit 2" onChange={(e) => setTitle(e.target.value)} />
        </label>
        <div className="assess-form-row">
          <label>Questions are
            <select value={type} onChange={(e) => setType(e.target.value as QuestionType)}>
              {(Object.keys(QUESTION_TYPE_LABELS) as QuestionType[]).map((key) => <option key={key} value={key}>{QUESTION_TYPE_LABELS[key]}</option>)}
            </select>
          </label>
          <label>Number of questions
            <input type="number" min={1} max={50} value={count} onChange={(e) => setCount(Math.max(1, Math.min(50, Number(e.target.value) || 1)))} />
          </label>
          <label>Seconds per question
            <input type="number" min={20} max={600} step={10} value={seconds} onChange={(e) => setSeconds(Math.max(20, Math.min(600, Number(e.target.value) || 20)))} />
          </label>
        </div>
        <label>Focus <small>(optional)</small>
          <textarea rows={2} maxLength={2000} value={instructions} placeholder="e.g. Only chapters 3 and 4. Mix easy and hard questions."
            onChange={(e) => setInstructions(e.target.value)} style={{ width: "100%", padding: "9px 11px", borderRadius: 10, border: "1px solid var(--line-1)", background: "var(--surf-2)", color: "var(--tx-1)", font: "inherit" }} />
        </label>
        <button className="btn btn-primary" disabled={busy}>{busy ? "Creating…" : "Create and add documents"}</button>
      </form>
    </section>
  );
}

function QuestionItem({ orgId, testId, q, locked, onChanged, onDeleted, onToast }: {
  orgId: string; testId: string; q: KnowledgeQuestion; locked: boolean;
  onChanged: (q: KnowledgeQuestion) => void; onDeleted: (test: KnowledgeTest) => void; onToast: (m: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(q);
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      onChanged(await updateKnowledgeQuestion(orgId, testId, q.id, q.qtype === "mcq"
        ? { question: draft.question, options: draft.options, correct: draft.correct ?? 0, explanation: draft.explanation }
        : { question: draft.question, answer: draft.answer, explanation: draft.explanation }));
      setEditing(false);
    } catch (err) {
      onToast((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm("Delete this question?")) return;
    try {
      onDeleted(await deleteKnowledgeQuestion(orgId, testId, q.id));
    } catch (err) {
      onToast((err as Error).message);
    }
  }

  return (
    <div className="kt-q">
      <div className="kt-q-head">
        <p>{q.position}. {q.question} <span className="assess-sub">· {q.qtype === "mcq" ? "Multiple choice" : "Q&A"}</span></p>
        {!locked && !editing && (
          <div className="org-actions">
            <button type="button" className="link-btn" onClick={() => { setDraft(q); setEditing(true); }}>Edit</button>
            <button type="button" className="link-btn" onClick={() => void remove()}>Delete</button>
          </div>
        )}
      </div>
      {!editing && (q.qtype === "mcq"
        ? <ol type="A">{q.options.map((option, i) => <li key={i} className={i === q.correct ? "right" : ""}>{option}{i === q.correct ? " ✓" : ""}</li>)}</ol>
        : <p className="kt-answer"><b>Answer:</b> {q.answer}</p>)}
      {!editing && q.explanation && <p className="assess-sub" style={{ margin: "6px 0 0" }}>{q.explanation}</p>}
      {editing && (
        <div className="kt-q-edit">
          <textarea rows={2} value={draft.question} onChange={(e) => setDraft({ ...draft, question: e.target.value })} aria-label="Question" />
          {q.qtype === "mcq" ? draft.options.map((option, i) => (
            <div key={i} className="kt-opt-row">
              <input type="radio" name={`right-${q.id}`} checked={draft.correct === i} onChange={() => setDraft({ ...draft, correct: i })} aria-label={`Option ${LETTERS[i]} is right`} />
              <b>{LETTERS[i]}</b>
              <input type="text" value={option} onChange={(e) => setDraft({ ...draft, options: draft.options.map((o, j) => (j === i ? e.target.value : o)) })} aria-label={`Option ${LETTERS[i]}`} />
            </div>
          )) : (
            <textarea rows={3} value={draft.answer} onChange={(e) => setDraft({ ...draft, answer: e.target.value })} aria-label="Model answer" />
          )}
          <input type="text" value={draft.explanation} placeholder="Explanation (optional)" onChange={(e) => setDraft({ ...draft, explanation: e.target.value })} aria-label="Explanation" />
          <div className="org-actions">
            <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={() => void save()}>{busy ? "Saving…" : "Save"}</button>
            <button type="button" className="btn btn-outline btn-sm" onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}

function TestEditor({ orgId, testId, onBack, onToast, onCreateLink, onListChanged }: {
  orgId: string; testId: string; onBack: () => void; onToast: (m: string) => void;
  onCreateLink: (testId: string) => void; onListChanged: () => void;
}) {
  const [test, setTest] = useState<KnowledgeTest | null>(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState("");
  const [results, setResults] = useState<UploadResult[]>([]);
  const [over, setOver] = useState(false);
  const fileRef = useRef<HTMLInputElement | null>(null);

  const load = useCallback(() => {
    fetchKnowledgeTest(orgId, testId).then(setTest).catch((err) => setError((err as Error).message));
  }, [orgId, testId]);
  useEffect(load, [load]);

  // While the questions are being written, check every few seconds.
  useEffect(() => {
    if (test?.status !== "generating") return;
    const timer = window.setInterval(() => {
      fetchKnowledgeTest(orgId, testId).then((next) => {
        setTest(next);
        if (next.status === "ready") { onToast(`${next.question_count} questions are ready. Check them below.`); onListChanged(); }
        if (next.status === "failed") onListChanged();
      }).catch(() => {});
    }, 3000);
    return () => window.clearInterval(timer);
  }, [test?.status, orgId, testId, onToast, onListChanged]);

  async function upload(files: FileList | File[]) {
    const list = Array.from(files);
    if (!list.length) return;
    const done: UploadResult[] = [];
    // One file per request: large decks stay under the server's upload limit.
    for (const [i, file] of list.entries()) {
      setUploading(`Reading ${file.name} (${i + 1} of ${list.length})…`);
      try {
        const response = await uploadKnowledgeDocument(orgId, testId, file);
        done.push(...response.results);
        setTest(response.test);
      } catch (err) {
        done.push({ filename: file.name, ok: false, message: (err as Error).message });
      }
    }
    setUploading("");
    setResults(done);
    onListChanged();
    if (fileRef.current) fileRef.current.value = "";
  }

  async function generate() {
    try {
      setTest(await generateKnowledgeQuestions(orgId, testId));
    } catch (err) {
      onToast((err as Error).message);
    }
  }

  async function change(body: Parameters<typeof updateKnowledgeTest>[2]) {
    try {
      setTest(await updateKnowledgeTest(orgId, testId, body));
      onListChanged();
    } catch (err) {
      onToast((err as Error).message);
    }
  }

  async function removeTest() {
    if (!test || !window.confirm(`Delete "${test.title}"? Its assessment links stop working.`)) return;
    try {
      await deleteKnowledgeTest(orgId, testId);
      onToast("Test deleted.");
      onListChanged();
      onBack();
    } catch (err) {
      onToast((err as Error).message);
    }
  }

  if (error) return <section className="org-card"><p className="form-error" role="alert">{error}</p><button type="button" className="btn btn-outline btn-sm" onClick={onBack}>Back</button></section>;
  if (!test) return <div className="org-skeleton tall" />;
  const generating = test.status === "generating";
  const docs = test.documents ?? [];
  const questions = test.questions ?? [];

  return (
    <div className="kt-builder">
      <section className="org-card">
        <div className="org-card-head">
          <div>
            <button type="button" className="link-btn" onClick={onBack}>← All knowledge tests</button>
            <h3 style={{ marginTop: 6 }}>{test.title}</h3>
          </div>
          <div className="org-actions">
            <span className={`kt-status kt-status-${test.status}`}>{STATUS_TEXT[test.status]}</span>
            <button type="button" className="link-btn" onClick={() => void removeTest()}>Delete test</button>
          </div>
        </div>
        {test.locked && <p className="org-notice">Learners have taken this test, so its documents and questions can no longer change. Create a new test to change them.</p>}
        <div className="assess-form-row assess-form">
          <label>Questions are
            <select value={test.question_type} disabled={test.locked || generating} onChange={(e) => void change({ question_type: e.target.value as QuestionType })}>
              {(Object.keys(QUESTION_TYPE_LABELS) as QuestionType[]).map((key) => <option key={key} value={key}>{QUESTION_TYPE_LABELS[key]}</option>)}
            </select>
          </label>
          <label>Number of questions
            <input type="number" min={1} max={50} defaultValue={test.num_questions} disabled={test.locked || generating}
              onBlur={(e) => { const n = Math.max(1, Math.min(50, Number(e.target.value) || 1)); if (n !== test.num_questions) void change({ num_questions: n }); }} />
          </label>
          <label>Seconds per question
            <input type="number" min={20} max={600} step={10} defaultValue={test.seconds_per_question}
              onBlur={(e) => { const n = Math.max(20, Math.min(600, Number(e.target.value) || 20)); if (n !== test.seconds_per_question) void change({ seconds_per_question: n }); }} />
          </label>
        </div>
      </section>

      <section className="org-card">
        <h3>1. Documents</h3>
        {!test.locked && (
          <div className={`kt-drop${over ? " over" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
            onDrop={(e) => { e.preventDefault(); setOver(false); if (!uploading) void upload(e.dataTransfer.files); }}>
            <b>Drop files here or choose them</b>
            <span className="assess-sub">PDF, Word (.docx), PowerPoint (.pptx), text, or images (PNG, JPG) · up to 20 MB each · up to 15 files</span>
            <input ref={fileRef} type="file" multiple accept={ACCEPT} disabled={Boolean(uploading)} onChange={(e) => e.target.files && void upload(e.target.files)} aria-label="Choose documents" />
            {uploading && <span aria-live="polite">{uploading}</span>}
          </div>
        )}
        {results.length > 0 && (
          <ul className="kt-upload-msgs">
            {results.map((r, i) => <li key={`${r.filename}-${i}`} className={r.ok ? "" : "bad"}>{r.ok ? `${r.filename}: read (${(r.chars ?? 0).toLocaleString()} characters)` : r.message}</li>)}
          </ul>
        )}
        <ul className="kt-docs">
          {docs.map((d) => (
            <li key={d.id}>
              <span><b>{d.filename}</b> <span className="assess-sub">· {d.kind.toUpperCase()} · {d.chars.toLocaleString()} characters</span></span>
              {!test.locked && <button type="button" className="link-btn" onClick={() => void deleteKnowledgeDocument(orgId, testId, d.id).then(setTest).catch((err) => onToast((err as Error).message))}>Remove</button>}
            </li>
          ))}
          {docs.length === 0 && <li className="assess-sub">No documents yet.</li>}
        </ul>
      </section>

      <section className="org-card">
        <div className="org-card-head">
          <h3>2. Questions and answers</h3>
          {!test.locked && (
            <button type="button" className="btn btn-primary btn-sm" disabled={generating || docs.length === 0 || Boolean(uploading)} onClick={() => void generate()}>
              {generating ? "Writing questions…" : questions.length ? "Write new questions" : `Write ${test.num_questions} questions`}
            </button>
          )}
        </div>
        {generating && <p className="rd-muted" aria-live="polite"><span className="kt-spinner" style={{ display: "inline-block", width: 16, height: 16, verticalAlign: "middle", marginRight: 8 }} />The AI is reading your documents and writing questions. This takes up to a minute or two.</p>}
        {test.error && <p className="org-notice">{test.error}</p>}
        {!generating && questions.length === 0 && <p className="assess-sub">{docs.length ? "Press the button to write the questions." : "Add documents first."}</p>}
        {questions.length > 0 && !generating && (
          <>
            <p className="assess-sub">Writing new questions replaces these. Check each answer before sharing the test.</p>
            {questions.map((q) => (
              <QuestionItem key={q.id} orgId={orgId} testId={testId} q={q} locked={test.locked} onToast={onToast}
                onChanged={(next) => setTest({ ...test, questions: questions.map((item) => (item.id === next.id ? next : item)) })}
                onDeleted={(next) => { setTest(next); onListChanged(); }} />
            ))}
          </>
        )}
      </section>

      {test.status === "ready" && questions.length > 0 && (
        <section className="org-card">
          <h3>3. Share it</h3>
          <p className="rd-muted">Create an assessment link for this test. Learners open it, agree to proctoring and take the test one question at a time, then get their report.</p>
          <button type="button" className="btn btn-primary" onClick={() => onCreateLink(test.id)}>Create assessment link</button>
        </section>
      )}
    </div>
  );
}

/** An organization admin's knowledge tests: build from documents, check, share. */
export default function OrgKnowledgeTests({ orgId, onToast, onCreateLink }: Props) {
  const [tests, setTests] = useState<KnowledgeTest[] | null>(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  const load = useCallback(() => {
    fetchKnowledgeTests(orgId).then(setTests).catch((err) => setError((err as Error).message));
  }, [orgId]);
  useEffect(load, [load]);

  if (open) return <TestEditor orgId={orgId} testId={open} onBack={() => setOpen(null)} onToast={onToast} onCreateLink={onCreateLink} onListChanged={load} />;
  return (
    <div className="kt-builder">
      <CreateTest orgId={orgId} onToast={onToast} onCreated={(test) => { load(); setOpen(test.id); }} />
      <section className="org-card">
        <h3>Your knowledge tests</h3>
        {error && <p className="form-error" role="alert">{error}</p>}
        {tests === null && !error && <div className="org-skeleton" />}
        {tests?.length === 0 && <p className="org-empty">No knowledge tests yet.</p>}
        <div className="kt-test-list">
          {tests?.map((test) => (
            <div key={test.id} className="kt-test-item">
              <div>
                <b>{test.title}</b>
                <div className="assess-sub">{QUESTION_TYPE_LABELS[test.question_type]} · {test.question_count} questions · {test.document_count} documents · {formatWhen(test.updated_at)}</div>
              </div>
              <div className="org-actions">
                <span className={`kt-status kt-status-${test.status}`}>{STATUS_TEXT[test.status]}</span>
                <button type="button" className="btn btn-outline btn-sm" onClick={() => setOpen(test.id)}>Open</button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
