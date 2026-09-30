import { render, screen } from "@testing-library/react";
import JobFetchDashboard, { jobProfileProgress } from "../../src/components/JobFetchDashboard";
import type { JobFetchFlowState } from "../../src/lib/jobFetchFlow";
import type { User } from "../../src/types";

jest.mock("../../src/lib/jobFetchApi", () => ({
  getSavedJobFetchJobs: jest.fn().mockResolvedValue({ jobs: [] }),
  getJobFetchApplications: jest.fn().mockResolvedValue({ applications: [] }),
  getHiddenJobFetchJobs: jest.fn().mockResolvedValue({ jobs: [] }),
}));

const incomplete: JobFetchFlowState = {
  step: "browsing", profileCompleted: false, experienceProvided: false,
  fullName: "", skills: [], preferredTitles: [], preferredLocations: [],
  preferredWorkMode: "", planTier: "free", feed: [],
};

test("dashboard does not show completion or invented preferences for a new account", () => {
  render(<JobFetchDashboard user={{ name: "Dhanush Lakshman" } as User} state={incomplete} onClose={() => {}} />);
  expect(screen.getByText("Building profile")).toBeInTheDocument();
  expect(screen.getByText("0%")).toBeInTheDocument();
  expect(screen.getAllByText("Not provided")).toHaveLength(3);
  expect(screen.queryByText("Any")).not.toBeInTheDocument();
  expect(screen.queryByText("Feed")).not.toBeInTheDocument();
});

test("only server-confirmed completion reaches 100 percent", () => {
  const facts: JobFetchFlowState = { ...incomplete, fullName: "Dhanush", skills: ["Python"],
    experienceProvided: true, experienceYears: 1.6, preferredTitles: ["AI Engineer"],
    preferredLocations: ["Chennai"], preferredWorkMode: "office" };
  expect(jobProfileProgress(facts)).toEqual({ complete: false, percent: 83 });
  expect(jobProfileProgress({ ...facts, profileCompleted: true })).toEqual({ complete: true, percent: 100 });
  expect(jobProfileProgress({ ...facts, preferredLocations: [] })).toEqual({ complete: false, percent: 67 });
});
