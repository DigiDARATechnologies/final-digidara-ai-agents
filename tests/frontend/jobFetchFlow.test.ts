import { handleJobFetchText, safeJobApplyUrl, type JobFetchFlowState } from "../../src/lib/jobFetchFlow";
import type { JobFeedItem } from "../../src/lib/jobFetchApi";

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

function sampleJob(overrides: Partial<JobFeedItem> = {}): JobFeedItem {
  return {
    id: 1,
    title: "Junior Developer",
    company: "Example Co",
    location: "Chennai",
    work_mode: "hybrid",
    employment_type: "full-time",
    apply_url: "https://example.com/jobs/1",
    description: "Build things.",
    skills: ["Python"],
    match_score: 80,
    match_reasons: ["Matches your preferred role"],
    is_saved: 0,
    application_status: null,
    ...overrides,
  };
}

function browsingState(feed: JobFeedItem[]): JobFetchFlowState {
  return {
    step: "browsing",
    fullName: "Test User",
    skills: ["Python"],
    preferredTitles: ["Developer"],
    preferredLocations: [],
    preferredWorkMode: "",
    planTier: "free",
    feed,
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

  test("job detail view offers an Apply now option and link for a safe apply_url", async () => {
    const job = sampleJob({ apply_url: "https://example.com/jobs/1" });
    const result = await handleJobFetchText(browsingState([job]), "detail:1");

    expect(result.messages[0].text).toContain("Apply here: https://example.com/jobs/1");
    expect(result.messages[0].options).toContainEqual(
      expect.objectContaining({ label: "Apply now ↗", value: "open:https://example.com/jobs/1" }),
    );
  });

  test("job detail view never renders or opens an unsafe apply_url", async () => {
    // Regression: a scraped job with a javascript: apply_url must not reach
    // the chat as a clickable link or an "open:" option — the backend
    // already rejects this at ingestion, but the render side must not rely
    // on that alone, since job data ultimately comes from third-party
    // sources DigiDARA does not control.
    const job = sampleJob({ apply_url: "javascript:alert(document.cookie)" });
    const result = await handleJobFetchText(browsingState([job]), "detail:1");

    expect(result.messages[0].text).not.toContain("javascript:");
    expect(result.messages[0].text).not.toContain("Apply here:");
    expect(result.messages[0].options?.some((option) => option.label === "Apply now ↗")).toBe(false);
    expect(result.messages[0].options?.some((option) => option.value.startsWith("open:javascript:"))).toBe(false);
  });
});
