import { useCallback, useEffect, useState, type FormEvent } from "react";
import { LEVEL_IDS, LEVEL_LABELS, type LevelId } from "../../lib/learnerApi";
import {
  createAssessment, fetchAssessmentAttempts, fetchAssessments, setAssessmentActive,
  type Assessment, type ProctorSettings, type ProctorSummary,
} from "../../lib/proctorApi";
import { formatWhen as when } from "../../lib/proctoring";
import { fetchKnowledgeTests, QUESTION_TYPE_LABELS, type KnowledgeTest } from "../../lib/knowledgeApi";
import { ProctorReport, ProctorTable } from "./ProctorReview";
import "../Proctor.css";

const CHECK_LABELS: { key: keyof Omit<ProctorSettings, "max_warnings">; label: string }[] = [
  { key: "fullscreen", label: "Full screen" },
  { key: "tab", label: "Tab switching" },
  { key: "copy_paste", label: "Block copy / paste" },
  { key: "webcam", label: "Webcam photos" },
  { key: "face", label: "Face check (AI)" },
];
const DEFAULT_CHECKS: ProctorSettings = { tab: true, fullscreen: true, copy_paste: true, webcam: true, face: true, max_warnings: 3 };

function linkFor(assessment: Assessment): string {
  return `${window.location.origin}${assessment.path}`;
}

function describe(assessment: Assessment): string {
  const { config } = assessment;
  if (assessment.kind === "knowledge_test") {
    return `Knowledge test: ${config.test_title ?? ""} · ${config.num_questions} questions · ${QUESTION_TYPE_LABELS[config.question_type ?? "mcq"]}`;
  }
  const what = config.round_type === "hr" ? "HR interview" : config.role_name ? `${config.role_name} interview` : `${config.subject} interview`;
  return `${what} · ${config.num_questions} questions · ${config.level_label ?? config.level}`;
}

/** A datetime-local value (the admin's own time) as UTC ISO, or null. */
function toIso(local: string): string | null {
  return local ? new Date(local).toISOString() : null;
}

function CreateForm({ orgId, presetTestId, onCreated, onToast }: {
  orgId: string; presetTestId?: string | null; onCreated: (a: Assessment) => void; onToast: (m: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<"mock_interview" | "knowledge_test">(presetTestId ? "knowledge_test" : "mock_interview");
  const [tests, setTests] = useState<KnowledgeTest[]>([]);
  const [testId, setTestId] = useState(presetTestId ?? "");
  useEffect(() => {
    fetchKnowledgeTests(orgId).then((all) => {
      const ready = all.filter((t) => t.status === "ready" && t.question_count > 0);
      setTests(ready);
      const chosen = ready.find((t) => t.id === presetTestId);
      if (chosen) setTitle((current) => current || chosen.title);
    }).catch(() => setTests([]));
  }, [orgId, presetTestId]);
  const [roundType, setRoundType] = useState<"technical" | "hr">("technical");
  const [focus, setFocus] = useState<"role" | "topic">("role");
  const [focusValue, setFocusValue] = useState("");
  const [questions, setQuestions] = useState<5 | 10 | 15>(10);
  const [level, setLevel] = useState<LevelId>("hard");
  const [opensAt, setOpensAt] = useState("");
  const [closesAt, setClosesAt] = useState("");
  const [membersOnly, setMembersOnly] = useState(true);
  const [checks, setChecks] = useState<ProctorSettings>(DEFAULT_CHECKS);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const created = await createAssessment(orgId, kind === "knowledge_test" ? {
        title, kind, config: { test_id: testId },
        proctoring: { ...checks, face: checks.webcam && checks.face },
        opens_at: toIso(opensAt), closes_at: toIso(closesAt), members_only: membersOnly,
      } : {
        title,
        config: {
          round_type: roundType,
          role_name: roundType === "technical" && focus === "role" ? focusValue.trim() : "",
          subject: roundType === "technical" && focus === "topic" ? focusValue.trim() : "",
          num_questions: questions, level,
        },
        proctoring: { ...checks, face: checks.webcam && checks.face },
        opens_at: toIso(opensAt), closes_at: toIso(closesAt), members_only: membersOnly,
      });
      void navigator.clipboard?.writeText(linkFor(created)).catch(() => {});
      onToast("Assessment link created and copied. Share it with your learners.");
      setTitle("");
      setFocusValue("");
      onCreated(created);
    } catch (err) {
      onToast((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="org-card">
      <h3>Create an assessment link</h3>
      <p className="rd-muted">Learners open the link, sign in, agree to proctoring and take the interview here on DigiDARA.
        You see each learner&apos;s score, integrity score, warnings and camera photos.</p>
      <form className="assess-form" onSubmit={submit}>
        <label>Title
          <input type="text" value={title} required minLength={3} maxLength={200} placeholder="e.g. Placement drive – round 1" onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label>Test
          <select value={kind} onChange={(e) => setKind(e.target.value as "mock_interview" | "knowledge_test")}>
            <option value="mock_interview">Mock interview</option>
            <option value="knowledge_test">Knowledge test (from your documents)</option>
          </select>
        </label>
        {kind === "knowledge_test" && (
          <label>Knowledge test
            <select value={testId} required onChange={(e) => setTestId(e.target.value)}>
              <option value="">Choose a test…</option>
              {tests.map((t) => <option key={t.id} value={t.id}>{t.title} ({t.question_count} questions)</option>)}
            </select>
            {tests.length === 0 && <small>No ready knowledge tests yet. Build one in the Knowledge tests tab.</small>}
          </label>
        )}
        {kind === "mock_interview" && <>
        <div className="assess-form-row">
          <label>Interview
            <select value={roundType} onChange={(e) => setRoundType(e.target.value as "technical" | "hr")}>
              <option value="technical">Technical interview</option>
              <option value="hr">HR interview</option>
            </select>
          </label>
          {roundType === "technical" && (
            <label>Based on
              <select value={focus} onChange={(e) => setFocus(e.target.value as "role" | "topic")}>
                <option value="role">A job role</option>
                <option value="topic">One topic</option>
              </select>
            </label>
          )}
          {roundType === "technical" && (
            <label>{focus === "role" ? "Job role" : "Topic"}
              <input type="text" value={focusValue} required maxLength={150} placeholder={focus === "role" ? "e.g. Data Analyst" : "e.g. Python"} onChange={(e) => setFocusValue(e.target.value)} />
            </label>
          )}
        </div>
        <div className="assess-form-row">
          <label>Questions
            <select value={questions} onChange={(e) => setQuestions(Number(e.target.value) as 5 | 10 | 15)}>
              {[5, 10, 15].map((count) => <option key={count} value={count}>{count}</option>)}
            </select>
          </label>
          <label>Level
            <select value={level} onChange={(e) => setLevel(e.target.value as LevelId)}>
              {LEVEL_IDS.map((id) => <option key={id} value={id}>{LEVEL_LABELS[id]}</option>)}
            </select>
          </label>
        </div>
        </>}
        <div className="assess-form-row">
          <label>Opens <small>(optional)</small>
            <input type="datetime-local" value={opensAt} onChange={(e) => setOpensAt(e.target.value)} />
          </label>
          <label>Closes <small>(optional)</small>
            <input type="datetime-local" value={closesAt} onChange={(e) => setClosesAt(e.target.value)} />
          </label>
        </div>
        <fieldset className="assess-checks" style={{ border: 0, padding: 0, margin: 0 }}>
          <legend className="rd-muted" style={{ marginBottom: 6 }}>Proctoring</legend>
          {CHECK_LABELS.map(({ key, label }) => (
            <label key={key}>
              <input type="checkbox" checked={checks[key] && (key !== "face" || checks.webcam)} disabled={key === "face" && !checks.webcam}
                onChange={(e) => setChecks((current) => ({ ...current, [key]: e.target.checked }))} />
              {label}
            </label>
          ))}
          <label>
            Warnings allowed
            <input type="number" min={1} max={10} value={checks.max_warnings} style={{ width: 64 }}
              onChange={(e) => setChecks((current) => ({ ...current, max_warnings: Math.max(1, Math.min(10, Number(e.target.value) || 1)) }))} />
          </label>
        </fieldset>
        <label className="proctor-agree" style={{ margin: 0 }}>
          <input type="checkbox" checked={membersOnly} onChange={(e) => setMembersOnly(e.target.checked)} />
          <span>Only members of this organization can take it</span>
        </label>
        <button className="btn btn-primary" disabled={busy}>{busy ? "Creating…" : "Create link"}</button>
      </form>
    </section>
  );
}

function AssessmentItem({ orgId, assessment, onChanged, onToast, onOpenReport }: {
  orgId: string; assessment: Assessment; onChanged: (a: Assessment) => void; onToast: (m: string) => void; onOpenReport: (id: string) => void;
}) {
  const [attempts, setAttempts] = useState<ProctorSummary[] | null>(null);
  const [open, setOpen] = useState(false);

  async function toggleResults() {
    const next = !open;
    setOpen(next);
    if (next) {
      try {
        setAttempts(await fetchAssessmentAttempts(orgId, assessment.id));
      } catch (err) {
        onToast((err as Error).message);
      }
    }
  }

  async function toggleActive() {
    try {
      onChanged(await setAssessmentActive(orgId, assessment.id, !assessment.active));
      onToast(assessment.active ? "The link no longer works." : "The link works again.");
    } catch (err) {
      onToast((err as Error).message);
    }
  }

  const window_ = [assessment.opens_at && `opens ${when(assessment.opens_at)}`, assessment.closes_at && `closes ${when(assessment.closes_at)}`].filter(Boolean).join(" · ");
  return (
    <section className="org-card">
      <div className="assess-item-head">
        <h4>{assessment.title}{assessment.active ? "" : " (turned off)"}</h4>
        <span className="assess-sub">{assessment.attempts} attempt{assessment.attempts === 1 ? "" : "s"}</span>
      </div>
      <p className="assess-sub" style={{ margin: "4px 0 0" }}>{describe(assessment)}{window_ ? ` · ${window_}` : ""}{assessment.members_only ? " · members only" : " · anyone with the link"}</p>
      <div className="assess-link">
        <code>{linkFor(assessment)}</code>
        <button type="button" className="btn btn-outline btn-sm" onClick={() => { void navigator.clipboard?.writeText(linkFor(assessment)); onToast("Link copied."); }}>Copy link</button>
        <button type="button" className="btn btn-outline btn-sm" onClick={() => void toggleResults()}>{open ? "Hide results" : "Results"}</button>
        <button type="button" className="link-btn" onClick={() => void toggleActive()}>{assessment.active ? "Turn off" : "Turn on"}</button>
      </div>
      {open && (attempts ? <ProctorTable rows={attempts} showPerson onOpen={onOpenReport} /> : <div className="org-skeleton" style={{ marginTop: 10 }} />)}
    </section>
  );
}

/** The organization admin's assessment links and their results. */
export default function OrgAssessments({ orgId, onToast, presetTestId = null }: { orgId: string; onToast: (m: string) => void; presetTestId?: string | null }) {
  const [items, setItems] = useState<Assessment[] | null>(null);
  const [error, setError] = useState("");
  const [report, setReport] = useState<string | null>(null);

  const load = useCallback(() => {
    fetchAssessments(orgId).then(setItems).catch((err) => setError((err as Error).message));
  }, [orgId]);
  useEffect(load, [load]);

  return (
    <div>
      <CreateForm key={presetTestId ?? "new"} orgId={orgId} presetTestId={presetTestId} onToast={onToast} onCreated={(created) => setItems((current) => [created, ...(current ?? [])])} />
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="assess-list">
        {items === null && !error && <div className="org-skeleton" />}
        {items?.length === 0 && <p className="org-empty">No assessment links yet. Create one above.</p>}
        {items?.map((item) => (
          <AssessmentItem key={item.id} orgId={orgId} assessment={item} onToast={onToast} onOpenReport={setReport}
            onChanged={(next) => setItems((current) => (current ?? []).map((a) => (a.id === next.id ? { ...next, attempts: a.attempts } : a)))} />
        ))}
      </div>
      {report && <ProctorReport orgId={orgId} sessionId={report} onClose={() => setReport(null)} />}
    </div>
  );
}
