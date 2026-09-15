import { handleJobFetchText, safeJobApplyUrl, type JobFetchFlowState } from "../../src/lib/jobFetchFlow";

jest.mock("../../src/lib/jobFetchApi", () => ({}));

function workModeState(): JobFetchFlowState {
  return {
    step: "collecting_work_mode",
    fullName: "Test User",
    skills: ["Python"],
    preferredTitles: ["Developer"],
    preferredLocations: [],
    preferredWorkMode: "",
    planTier: "free",
    feed: [],
  };
}

describe("Job Fetching Agent flow", () => {
  test.each([
    ["remote", "remote"],
    ["hybrid", "hybrid"],
    ["onsite", "onsite"],
    ["any", ""],
  ])("accepts the %s work mode option", async (input, expected) => {
    const result = await handleJobFetchText(workModeState(), input);
    expect(result.state.step).toBe("collecting_experience");
    expect(result.state.preferredWorkMode).toBe(expected);
  });

  test("accepts only HTTP application links", () => {
    expect(safeJobApplyUrl("https://example.com/jobs/1")).toBe("https://example.com/jobs/1");
    expect(safeJobApplyUrl("javascript:alert(1)")).toBeNull();
    expect(safeJobApplyUrl("not a url")).toBeNull();
  });
});
