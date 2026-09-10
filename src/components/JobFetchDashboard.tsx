import { useEffect, useState } from "react";
import {
  getHiddenJobFetchJobs,
  getJobFetchApplications,
  getSavedJobFetchJobs,
  jobFetchAction,
  type AppliedJobItem,
  type HiddenJobItem,
  type SavedJobItem,
} from "../lib/jobFetchApi";
import type { JobFetchFlowState } from "../lib/jobFetchFlow";
import type { User } from "../types";

interface JobFetchDashboardProps {
  user: User;
  state: JobFetchFlowState;
  onClose: () => void;
}

export default function JobFetchDashboard({ user, state, onClose }: JobFetchDashboardProps) {
  const [savedJobs, setSavedJobs] = useState<SavedJobItem[]>([]);
  const [savedError, setSavedError] = useState<string | null>(null);
  const [applications, setApplications] = useState<AppliedJobItem[]>([]);
  const [applicationsError, setApplicationsError] = useState<string | null>(null);
  const [hiddenJobs, setHiddenJobs] = useState<HiddenJobItem[]>([]);
  const [hiddenError, setHiddenError] = useState<string | null>(null);
  const [unhidingId, setUnhidingId] = useState<number | null>(null);
  const profileSteps = ["collecting_name", "collecting_skills", "collecting_titles", "collecting_locations", "collecting_work_mode", "collecting_experience", "collecting_resume"];
  const profileProgress = state.step === "browsing" ? 100 : Math.round((profileSteps.indexOf(state.step) / profileSteps.length) * 100);

  useEffect(() => {
    let active = true;
    getSavedJobFetchJobs()
      .then((result) => active && setSavedJobs(result.jobs))
      .catch((error) => active && setSavedError((error as Error).message));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    getJobFetchApplications()
      .then((result) => active && setApplications(result.applications))
      .catch((error) => active && setApplicationsError((error as Error).message));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    getHiddenJobFetchJobs()
      .then((result) => active && setHiddenJobs(result.jobs))
      .catch((error) => active && setHiddenError((error as Error).message));
    return () => { active = false; };
  }, []);

  async function handleUnhide(jobId: number) {
    setUnhidingId(jobId);
    try {
      await jobFetchAction(jobId, "unhide");
      setHiddenJobs((current) => current.filter((job) => job.id !== jobId));
    } catch (error) {
      setHiddenError((error as Error).message);
    } finally {
      setUnhidingId(null);
    }
  }

  return (
    <aside className="agent-dashboard">
      <div className="dashboard-head">
        <div><span>Job Fetching Agent</span><h2>Career dashboard</h2></div>
        <button className="icon-btn" onClick={onClose} aria-label="Close dashboard">x</button>
      </div>

      <div className="dashboard-status-card">
        <div className="dashboard-status-row">
          <strong>{state.step === "browsing" ? "Browsing feed" : "Building profile"}</strong>
          <span>{profileProgress}%</span>
        </div>
        <div className="progress-track"><span style={{ width: `${profileProgress}%` }} /></div>
        <p>Jobs are scored against your skills, target titles, location, and work-mode preferences.</p>
      </div>

      <div className="dashboard-section">
        <h3>Profile</h3>
        <dl>
          <div><dt>Name</dt><dd>{state.fullName || user.name}</dd></div>
          <div><dt>Plan</dt><dd>{state.planTier === "pro" ? "Pro" : "Free"}</dd></div>
          <div><dt>Skills</dt><dd>{state.skills.length ? state.skills.join(", ") : "—"}</dd></div>
          <div><dt>Target titles</dt><dd>{state.preferredTitles.length ? state.preferredTitles.join(", ") : "—"}</dd></div>
          <div><dt>Locations</dt><dd>{state.preferredLocations.length ? state.preferredLocations.join(", ") : "Any"}</dd></div>
          <div><dt>Work mode</dt><dd>{state.preferredWorkMode || "Any"}</dd></div>
          <div><dt>Resume</dt><dd>{state.resumeOriginalName || "Not uploaded"}</dd></div>
        </dl>
      </div>

      {state.step === "browsing" && (
        <div className="dashboard-section">
          <h3>Feed</h3>
          <dl>
            <div><dt>Matched jobs</dt><dd>{state.feed.length}</dd></div>
            <div><dt>Saved</dt><dd>{savedJobs.length}</dd></div>
            <div><dt>Applied</dt><dd>{applications.length}</dd></div>
          </dl>
        </div>
      )}

      {savedJobs.length > 0 && (
        <div className="dashboard-section">
          <h3>Saved jobs</h3>
          <dl>
            {savedJobs.slice(0, 10).map((job) => (
              <div key={job.id} className="saved-job-row">
                <dt><a href={job.apply_url} target="_blank" rel="noreferrer">{job.title}</a></dt>
                <dd>{job.company}{job.application_status === "applied" ? " · Applied" : ""}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {!savedJobs.length && !savedError && state.step === "browsing" && (
        <div className="dashboard-section"><h3>Saved jobs</h3><p>No saved jobs yet. Save a job from its details to keep it here.</p></div>
      )}
      {savedError && <div className="dashboard-section"><h3>Saved jobs</h3><p>Saved jobs could not be loaded: {savedError}</p></div>}

      {applications.length > 0 && (
        <div className="dashboard-section">
          <h3>Applications</h3>
          <dl>
            {applications.slice(0, 10).map((job) => (
              <div key={job.id}>
                <dt><a href={job.apply_url} target="_blank" rel="noreferrer">{job.title}</a></dt>
                <dd>
                  {job.company}
                  {job.application_status ? ` · ${job.application_status[0].toUpperCase()}${job.application_status.slice(1)}` : ""}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {!applications.length && !applicationsError && state.step === "browsing" && (
        <div className="dashboard-section"><h3>Applications</h3><p>No applications yet. Applying to a job from its details will list it here.</p></div>
      )}
      {applicationsError && <div className="dashboard-section"><h3>Applications</h3><p>Applications could not be loaded: {applicationsError}</p></div>}

      {hiddenJobs.length > 0 && (
        <div className="dashboard-section">
          <h3>Hidden jobs</h3>
          <dl>
            {hiddenJobs.slice(0, 10).map((job) => (
              <div key={job.id} className="saved-job-row">
                <dt>{job.title}</dt>
                <dd>
                  {job.company}
                  {" · "}
                  <button
                    type="button"
                    className="link-btn"
                    disabled={unhidingId === job.id}
                    onClick={() => handleUnhide(job.id)}
                  >
                    {unhidingId === job.id ? "Unhiding…" : "Unhide"}
                  </button>
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {!hiddenJobs.length && !hiddenError && state.step === "browsing" && (
        <div className="dashboard-section"><h3>Hidden jobs</h3><p>No hidden jobs. Jobs you mark "Not interested" will show up here so you can undo it.</p></div>
      )}
      {hiddenError && <div className="dashboard-section"><h3>Hidden jobs</h3><p>Hidden jobs could not be loaded: {hiddenError}</p></div>}
    </aside>
  );
}
