import { handleJobFetchText, openJobFetchChat, safeJobApplyUrl, type JobFetchFlowState } from "../../src/lib/jobFetchFlow";
import type { User } from "../../src/types";
import type { JobFeedItem } from "../../src/lib/jobFetchApi";
import { chatWithJobAgent, getJobFeed, ensureJobFetchProfile, getJobFetchProfile } from "../../src/lib/jobFetchApi";

jest.mock("../../src/lib/jobFetchApi", () => ({
  getJobFeed: jest.fn(),
  chatWithJobAgent: jest.fn(),
  ensureJobFetchProfile: jest.fn(),
  getJobFetchProfile: jest.fn(),
}));

function workModeState(): JobFetchFlowState {
  return {
    step: "collecting_work_mode",
    profileCompleted: false,
    experienceProvided: false,
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
    profileCompleted: true,
    experienceProvided: true,
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
  test.each(["how are you?", "hi"])("legacy experience step acknowledges '%s' without advancing", async (text) => {
    const state = { ...workModeState(), step: "collecting_experience" as const };
    const result = await handleJobFetchText(state, text);
    expect(result.state).toEqual(state);
    expect(result.messages[0].text).toContain("fresher");
    expect(result.messages[0].text).toContain("ready");
  });

  test("legacy experience step accepts fresher after a greeting", async () => {
    const state = { ...workModeState(), step: "collecting_experience" as const };
    const greeting = await handleJobFetchText(state, "hi");
    const result = await handleJobFetchText(greeting.state, "fresher");
    expect(result.state.step).toBe("collecting_resume");
    expect(result.state.experienceYears).toBe(0);
  });

  test("legacy skills step never saves a greeting as a skill", async () => {
    const state = { ...workModeState(), step: "collecting_skills" as const, skills: [] };
    const result = await handleJobFetchText(state, "hi");
    expect(result.state).toEqual(state);
    expect(result.messages[0].text).toContain("technical skill");
  });

  test.each(["why you ask my name?", "what is the reason you need my name?"])("answers name purpose without saving '%s' as a name", async (text) => {
    const state = { ...workModeState(), step: "collecting_name" as const, fullName: "" };
    const result = await handleJobFetchText(state, text);
    expect(result.state).toEqual(state);
    expect(result.messages[0].text).toContain("name section");
    expect(result.messages[0].text).toContain("isn't fully complete");
    expect(result.messages[0].text).toContain("legal name");
  });

  test("declining a name does not finish or advance the legacy profile", async () => {
    const state = { ...workModeState(), step: "collecting_name" as const, fullName: "" };
    const result = await handleJobFetchText(state, "I don't want to give my name");
    expect(result.state).toEqual(state);
    expect(result.messages[0].text).toContain("you decide what to share");
    expect(result.messages[0].text).toContain("isn't fully complete");
  });

  test("provider names embedded in aggregator badges are hidden in candidate details", async () => {
    const job = sampleJob({ trust_badge: "Aggregator Listing (via RapidAPI JSearch)" });
    const result = await handleJobFetchText(browsingState([job]), "detail:1");
    expect(result.messages[0].text).toContain("Aggregator Listing");
    expect(result.messages[0].text).not.toContain("RapidAPI");
  });

  test("more matches after a contextual search uses conversation retrieval, not saved-location feed", async () => {
    jest.mocked(getJobFeed).mockClear();
    jest.mocked(chatWithJobAgent).mockResolvedValue({
      reply: "No further matching jobs", show_jobs: true, suggested_actions: [], matched_jobs: [],
      updated_profile: { skills: ["SQL"], preferred_titles: ["Data Analyst"], preferred_locations: ["Bengaluru"],
        preferred_work_mode: "office", experience_years: 0, changed_fields: [] },
      search_context: { titles: ["Machine Learning Engineer"], locations: ["Madurai"], work_mode: null, role_label: "Machine Learning" },
    });
    const result = await handleJobFetchText({ ...browsingState([]), contextualSearch: true }, "Show me more jobs");
    expect(getJobFeed).not.toHaveBeenCalled();
    expect(chatWithJobAgent).toHaveBeenCalledWith("Show me more jobs", [], undefined, undefined, expect.stringMatching(/^m_/));
    expect(result.state.contextualSearch).toBe(true);
    expect(result.state.preferredLocations).toEqual(["Bengaluru"]);
  });

  test.each(["Adzuna Job API", "RapidAPI JSearch"])("hides %s but retains caution in job details", async (provider) => {
    const job = sampleJob({ source_label: provider, trust_badge: "Review With Caution", trust_score: 20 });
    const result = await handleJobFetchText(browsingState([job]), "detail:1");
    expect(result.messages[0].text).not.toContain(provider);
    expect(result.messages[0].text).not.toContain("**Source:**");
    expect(result.messages[0].text).toContain("Review With Caution");
  });

  test("conversational job-card rendering hides the provider label", async () => {
    jest.mocked(chatWithJobAgent).mockResolvedValue({
      reply: "Here are your matches", show_jobs: true,
      updated_profile: { skills: [], preferred_titles: [], preferred_locations: [], preferred_work_mode: "", experience_years: 0, changed_fields: [] },
      suggested_actions: [], matched_jobs: [sampleJob({ source_label: "RapidAPI JSearch", trust_badge: "Review With Caution" })],
    });
    const result = await handleJobFetchText(browsingState([]), "show matching jobs");
    expect(result.messages[0].text).not.toContain("RapidAPI JSearch");
    expect(result.messages[0].text).not.toContain("**Source:**");
  });
  test("reopening an incomplete saved profile displays the server skills prompt", async () => {
    jest.mocked(ensureJobFetchProfile).mockResolvedValue({ user_id: "user-1" } as Awaited<ReturnType<typeof ensureJobFetchProfile>>);
    jest.mocked(getJobFetchProfile).mockResolvedValue({
      user_id: "user-1", full_name: "Dhanu", skills: [], preferred_titles: [],
      preferred_locations: [], preferred_work_mode: "", experience_years: 0,
      experience_provided: false, resume_url: "", resume_original_name: null,
      profile_completed: false, plan_tier: "free", onboarding_step: "skills",
      onboarding_prompt: "What are your primary technical **skills**?",
    });
    jest.mocked(getJobFeed).mockClear();
    const result = await openJobFetchChat({ name: "john" } as User);
    expect(result.messages[0].text).toContain("Hi Dhanu");
    expect(result.messages[0].text).toContain("primary technical **skills**");
    expect(result.messages[0].text).not.toContain("from your DigiDARA account");
    expect(result.messages[0].text).not.toContain("What name or nickname");
    expect(result.state.step).toBe("browsing");
    expect(result.state.profileCompleted).toBe(false);
    expect(getJobFeed).not.toHaveBeenCalled();
  });

  test("an incomplete account profile never becomes a completed browsing profile", async () => {
    jest.mocked(ensureJobFetchProfile).mockResolvedValue({ user_id: "user-1" } as Awaited<ReturnType<typeof ensureJobFetchProfile>>);
    jest.mocked(getJobFetchProfile).mockResolvedValue({
      user_id: "user-1", full_name: "", skills: [], preferred_titles: [],
      preferred_locations: [], preferred_work_mode: "", experience_years: 0,
      experience_provided: false, resume_url: "", resume_original_name: null,
      profile_completed: false, plan_tier: "free", onboarding_step: "full_name",
      onboarding_prompt: "Please enter a name or nickname.",
    });
    const opened = await openJobFetchChat({ name: "Dhanush Lakshman" } as User);
    expect(opened.messages[0].text).toContain("Hi Dhanush");
    expect(opened.state.fullName).toBe("");
    expect(opened.state.profileCompleted).toBe(false);
    expect(opened.state.experienceProvided).toBe(false);
  });

  test("a failed initial feed does not erase an already loaded profile", async () => {
    jest.mocked(ensureJobFetchProfile).mockResolvedValue({ user_id: "user-1" } as Awaited<ReturnType<typeof ensureJobFetchProfile>>);
    jest.mocked(getJobFetchProfile).mockResolvedValue({
      user_id: "user-1", full_name: "Dhanush", skills: ["Python"], preferred_titles: ["AI Engineer"],
      preferred_locations: ["Chennai"], preferred_work_mode: "office", experience_years: 1.6,
      experience_provided: true, resume_url: "", resume_original_name: null,
      profile_completed: true, plan_tier: "free", onboarding_step: "completed",
    });
    jest.mocked(getJobFeed).mockRejectedValueOnce(new Error("feed timeout"));
    const opened = await openJobFetchChat({ name: "Account Name" } as User);
    expect(opened.state.fullName).toBe("Dhanush");
    expect(opened.state.profileCompleted).toBe(true);
    expect(opened.state.feed).toEqual([]);
    expect(opened.messages[0].text).toContain("couldn't load your job feed");
    expect(opened.messages[0].text).not.toContain("could not connect");
  });

  test.each(["how are you", "send Python jobs"])('failed chat never turns "%s" into a feed search', async (message) => {
    const state = { ...browsingState([]), profileCompleted: false, fullName: "", skills: [],
      preferredTitles: [], experienceProvided: false };
    jest.mocked(chatWithJobAgent).mockRejectedValueOnce(new Error("upstream failure"));
    jest.mocked(getJobFeed).mockClear();
    const result = await handleJobFetchText(state, message);
    expect(getJobFeed).not.toHaveBeenCalled();
    expect(result.state).toEqual({ ...state, pendingChat: {
      message, clientMessageId: expect.stringMatching(/^m_/),
    } });
    expect(result.messages[0].text).toContain("couldn't confirm a reply");
    expect(result.messages[0].text).not.toContain("matching jobs for");
    expect(result.messages[0].options).toBeUndefined();
  });

  test("resending a failed message reuses its idempotency key and clears it on success", async () => {
    const state = { ...browsingState([]), profileCompleted: false };
    jest.mocked(chatWithJobAgent).mockRejectedValueOnce(new Error("response lost"));
    const failed = await handleJobFetchText(state, "how are you");
    jest.mocked(chatWithJobAgent).mockResolvedValueOnce({
      reply: "I'm here and ready to help. What name would you like me to use?",
      show_jobs: false, suggested_actions: [], matched_jobs: [],
      updated_profile: { full_name: "", skills: [], preferred_titles: [], preferred_locations: [],
        preferred_work_mode: "", experience_years: 0, experience_provided: false,
        profile_completed: false, changed_fields: [] },
    });
    const retried = await handleJobFetchText(failed.state, "how are you");
    const firstId = jest.mocked(chatWithJobAgent).mock.calls.at(-2)?.[4];
    const secondId = jest.mocked(chatWithJobAgent).mock.calls.at(-1)?.[4];
    expect(firstId).toMatch(/^m_/);
    expect(secondId).toBe(firstId);
    expect(retried.state.pendingChat).toBeUndefined();
    expect(retried.messages[0].text).toContain("ready to help");
    expect(getJobFeed).not.toHaveBeenCalled();
  });

  test.each(["refresh", "show me more jobs"])("an incomplete empty profile routes '%s' to chat, not the feed", async (message) => {
    const state = { ...browsingState([]), profileCompleted: false };
    jest.mocked(chatWithJobAgent).mockRejectedValueOnce(new Error("chat unavailable"));
    jest.mocked(getJobFeed).mockClear();
    await handleJobFetchText(state, message);
    expect(chatWithJobAgent).toHaveBeenCalled();
    expect(getJobFeed).not.toHaveBeenCalled();
  });
  test.each([
    ["remote", "remote"],
    ["hybrid", "hybrid"],
    ["onsite", "office"],
    ["office", "office"],
    ["any", "any"],
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

  test("Show me more jobs requests the next strict location page and appends it", async () => {
    const first = sampleJob();
    const second = sampleJob({ id: 2, title: "Python Developer" });
    jest.mocked(getJobFeed).mockResolvedValue({
      jobs: [second], total: 2, returned: 1, plan_tier: "free", limit: 5, offset: 1, has_more: false,
    });
    const state = {
      ...browsingState([first]),
      preferredLocations: ["Chennai"],
      feedOffset: 1,
      hasMore: true,
    };

    const result = await handleJobFetchText(state, "Show me more jobs");

    expect(getJobFeed).toHaveBeenCalledWith(expect.objectContaining({ location: "Chennai", limit: 5, offset: 1 }));
    expect(result.state.feed.map((job) => job.id)).toEqual([1, 2]);
    expect(result.state.hasMore).toBe(false);
  });

  test("rejects implausible experience without advancing", async () => {
    const state = { ...workModeState(), step: "collecting_experience" as const };
    const result = await handleJobFetchText(state, "100 years");
    expect(result.state.step).toBe("collecting_experience");
    expect(result.messages[0].text).toContain("between 0 and 50 years");
  });

  test("answers a skills-versus-role clarification without storing the question as a skill", async () => {
    const state = { ...workModeState(), step: "collecting_skills" as const, skills: [] };
    const result = await handleJobFetchText(state, "Are you asking role or my skills?");
    expect(result.state.step).toBe("collecting_skills");
    expect(result.state.skills).toEqual([]);
    expect(result.messages[0].text).toContain("asking for your skills");
  });

  test("forwards the server conversation id on conversational turns", async () => {
    jest.mocked(chatWithJobAgent).mockResolvedValue({
      reply: "Saved context",
      show_jobs: false,
      updated_profile: {
        full_name: "Dhanush",
        skills: ["Python"], preferred_locations: [], preferred_titles: ["Developer"],
        preferred_work_mode: "", experience_years: 1, changed_fields: [],
      },
      suggested_actions: [],
      matched_jobs: [],
      conversation_id: "chat-123",
      memory_status: "saved",
    });
    const state = { ...browsingState([]), conversationId: "chat-123" };
    const result = await handleJobFetchText(state, "How can I improve my resume?");
    expect(chatWithJobAgent).toHaveBeenCalledWith(
      "How can I improve my resume?", [], undefined, "chat-123", expect.stringMatching(/^m_/),
    );
    expect(result.state.conversationId).toBe("chat-123");
    expect(result.state.fullName).toBe("Dhanush");
  });
});
