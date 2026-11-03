import { useEffect, useMemo, useState } from "react";
import { fetchOrganizationProctoring, type ProctorSummary } from "../../lib/proctorApi";
import { ProctorReport, ProctorTable } from "./ProctorReview";

const TESTS = [
  { value: "", label: "All tests" },
  { value: "mock_interview_agent", label: "Mock interview" },
  { value: "capstone_project_agent", label: "Capstone viva" },
  { value: "knowledge_test_agent", label: "Knowledge test" },
];

/** Every proctored sitting of this organization's own students. "View" shows the
 * warnings and the camera photos. */
export default function OrgProctoring({ orgId }: { orgId: string }) {
  const [rows, setRows] = useState<ProctorSummary[] | null>(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [test, setTest] = useState("");
  const [onlyWarnings, setOnlyWarnings] = useState(false);
  const [report, setReport] = useState<string | null>(null);

  useEffect(() => {
    fetchOrganizationProctoring(orgId).then(setRows).catch((err) => setError((err as Error).message));
  }, [orgId]);

  const shown = useMemo(() => {
    const text = search.trim().toLowerCase();
    return (rows ?? []).filter((row) => (!test || row.agent_name === test)
      && (!onlyWarnings || row.warnings > 0)
      && (!text || row.name.toLowerCase().includes(text) || row.email.toLowerCase().includes(text)));
  }, [rows, search, test, onlyWarnings]);

  return (
    <section className="org-card">
      <div className="org-card-head">
        <h3>Proctoring</h3>
        <span className="rd-muted">Your students' proctored tests, with their warnings and camera photos. Practice tests appear for students who agreed to share their progress.</span>
      </div>
      <div className="org-filters" style={{ display: "flex", flexWrap: "wrap", gap: 8, margin: "10px 0" }}>
        <input type="search" aria-label="Search students" placeholder="Search name or email" value={search} onChange={(event) => setSearch(event.target.value)} />
        <select aria-label="Test" value={test} onChange={(event) => setTest(event.target.value)}>
          {TESTS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        <label><input type="checkbox" checked={onlyWarnings} onChange={(event) => setOnlyWarnings(event.target.checked)} /> Only with warnings</label>
      </div>
      {error && <p className="proctor-error" role="alert">{error}</p>}
      {!rows && !error && <div className="org-skeleton" />}
      {rows && <ProctorTable rows={shown} showPerson showTest onOpen={setReport} />}
      {report && <ProctorReport orgId={orgId} sessionId={report} onClose={() => setReport(null)} />}
    </section>
  );
}
