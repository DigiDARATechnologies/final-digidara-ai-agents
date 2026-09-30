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
import { safeJobApplyUrl, type JobFetchFlowState } from "../lib/jobFetchFlow";
import type { User } from "../types";

interface JobFetchDashboardProps {
  user: User;
  state: JobFetchFlowState;
  onClose: () => void;
}

export function jobProfileProgress(state: JobFetchFlowState): { complete: boolean; percent: number } {
  const hasLocation = state.preferredLocations.length > 0 || ["remote", "any"].includes(state.preferredWorkMode.toLowerCase());
  const savedFields = [Boolean(state.fullName.trim()), state.skills.length > 0,
    state.experienceProvided, state.preferredTitles.length > 0, hasLocation];
  const complete = state.profileCompleted && savedFields.every(Boolean);
  // The sixth step is the server-confirmed completion decision (including
  // resume upload or skip), not the client-side chat routing state.
  return { complete, percent: Math.round((savedFields.filter(Boolean).length + Number(complete)) / 6 * 100) };
}

export default function JobFetchDashboard({ state, onClose }: JobFetchDashboardProps) {
  const [savedJobs, setSavedJobs] = useState<SavedJobItem[]>([]);
  const [savedError, setSavedError] = useState<string | null>(null);
  const [applications, setApplications] = useState<AppliedJobItem[]>([]);
  const [applicationsError, setApplicationsError] = useState<string | null>(null);
  const [hiddenJobs, setHiddenJobs] = useState<HiddenJobItem[]>([]);
  const [hiddenError, setHiddenError] = useState<string | null>(null);
  const [unhidingId, setUnhidingId] = useState<number | null>(null);
  const profileProgress = jobProfileProgress(state);

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
        <div><span>Job Fetching Agent</span><h2>Career Dashboard</h2></div>
        <button className="icon-btn" onClick={onClose} aria-label="Close dashboard">x</button>
      </div>

      <div className="dashboard-status-card">
        <div className="dashboard-status-row">
          <strong>{profileProgress.complete ? "Browsing feed" : "Building profile"}</strong>
          <span>{profileProgress.percent}%</span>
        </div>
        <div className="progress-track"><span style={{ width: `${profileProgress.percent}%` }} /></div>
        <p>Jobs are scored against your skills, target titles, location, and work-mode preferences.</p>
      </div>

      <div className="dashboard-section">
        <h3>Profile</h3>
        <dl>
          <div><dt>Name</dt><dd>{state.fullName || "Not provided"}</dd></div>
          <div><dt>Plan</dt><dd>{state.planTier === "pro" ? "Pro" : "Free"}</dd></div>
          <div><dt>Skills</dt><dd>{state.skills.length ? state.skills.join(", ") : "—"}</dd></div>
          <div><dt>Target Titles</dt><dd>{state.preferredTitles.length ? state.preferredTitles.join(", ") : "—"}</dd></div>
          <div><dt>Locations</dt><dd>{state.preferredLocations.length ? state.preferredLocations.join(", ") : state.preferredWorkMode === "remote" ? "Remote" : state.preferredWorkMode === "any" ? "Any location" : "Not provided"}</dd></div>
          <div><dt>Work Mode</dt><dd>{state.preferredWorkMode || "Not provided"}</dd></div>
          <div><dt>Resume</dt><dd>{state.resumeOriginalName || "Not uploaded"}</dd></div>
        </dl>
      </div>

      {(profileProgress.complete || state.feed.length > 0) && (
        <div className="dashboard-section">
          <h3>Feed</h3>
          <dl>
            <div><dt>Matched Jobs</dt><dd>{state.feed.length}</dd></div>
            <div><dt>Saved</dt><dd>{savedJobs.length}</dd></div>
            <div><dt>Applied</dt><dd>{applications.length}</dd></div>
          </dl>
        </div>
      )}

      {savedJobs.length > 0 && (
        <div className="dashboard-section">
          <h3>Saved Jobs</h3>
          <dl>
            {savedJobs.slice(0, 10).map((job) => {
              const safeApplyUrl = safeJobApplyUrl(job.apply_url);
              return (
                <div key={job.id} className="saved-job-row">
                  <dt>{safeApplyUrl ? <a href={safeApplyUrl} target="_blank" rel="noreferrer">{job.title}</a> : job.title}</dt>
                  <dd>{job.company}{job.application_status === "applied" ? " · Applied" : ""}</dd>
                </div>
              );
            })}
          </dl>
        </div>
      )}

      {!savedJobs.length && !savedError && state.step === "browsing" && (
        <div className="dashboard-section"><h3>Saved Jobs</h3><p>No saved jobs yet. Save a job from its details to keep it here.</p></div>
      )}
      {savedError && <div className="dashboard-section"><h3>Saved Jobs</h3><p>Saved jobs could not be loaded: {savedError}</p></div>}

      {applications.length > 0 && (
        <div className="dashboard-section">
          <h3>Applications</h3>
          <dl>
            {applications.slice(0, 10).map((job) => {
              const safeApplyUrl = safeJobApplyUrl(job.apply_url);
              return (
                <div key={job.id}>
                  <dt>{safeApplyUrl ? <a href={safeApplyUrl} target="_blank" rel="noreferrer">{job.title}</a> : job.title}</dt>
                  <dd>
                    {job.company}
                    {job.application_status ? ` · ${job.application_status[0].toUpperCase()}${job.application_status.slice(1)}` : ""}
                  </dd>
                </div>
              );
            })}
          </dl>
        </div>
      )}

      {!applications.length && !applicationsError && state.step === "browsing" && (
        <div className="dashboard-section"><h3>Applications</h3><p>No applications yet. Applying to a job from its details will list it here.</p></div>
      )}
      {applicationsError && <div className="dashboard-section"><h3>Applications</h3><p>Applications could not be loaded: {applicationsError}</p></div>}

      {hiddenJobs.length > 0 && (
        <div className="dashboard-section">
          <h3>Hidden Jobs</h3>
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

      {!hiddenJobs.length && !hiddenError && profileProgress.complete && (
        <div className="dashboard-section"><h3>Hidden Jobs</h3><p>No hidden jobs. Jobs you mark "Not interested" will show up here so you can undo it.</p></div>
      )}
      {hiddenError && <div className="dashboard-section"><h3>Hidden Jobs</h3><p>Hidden jobs could not be loaded: {hiddenError}</p></div>}
    </aside>
  );
}
