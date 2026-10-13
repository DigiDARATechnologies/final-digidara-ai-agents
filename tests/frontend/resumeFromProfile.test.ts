/** Resume Builder: "Build from my DigiDARA profile" fills the draft from what
 * the other agents know and asks only what is missing. */
jest.mock("../../src/lib/resumeBuilderApi", () => ({
  ensureResumeProfile: jest.fn().mockResolvedValue({ user_id: "u1" }),
  fetchResumeFacts: jest.fn(),
  createResume: jest.fn(), getResume: jest.fn(), updateResume: jest.fn(), suggestResumeWording: jest.fn().mockResolvedValue({ suggestion: "" }),
  resumeChatTurn: jest.fn(), suggestResumeEdit: jest.fn(), analyzeResumeUpload: jest.fn(), createImportDraft: jest.fn(),
  generateImportedResume: jest.fn(), analyzeSavedResume: jest.fn(), listResumeTemplates: jest.fn(), selectResumeTemplate: jest.fn(),
}));

import * as api from "../../src/lib/resumeBuilderApi";
import { draftFromResumeFacts, handleResumeBuilderText, openResumeBuilderChat } from "../../src/lib/resumeBuilderFlow";
import { setLearnerContext } from "../../src/lib/learnerContext";
import type { LearnerSummary } from "../../src/lib/learnerApi";

const user = { id: "u1", name: "Prem Kumar", email: "prem@example.com", mobile: "", initial: "P" };

const FACTS = {
  name: "Prem Kumar", email: "prem@example.com", phone: "", target_role: "data analyst", degree: "B.Sc Computer Science",
  experience_level: "fresher" as const, skills: ["SQL", "Python"],
  projects: [{ title: "Sales Dashboard", description: "Tracks monthly sales.", skills: ["Power BI", "sql"], score: 82 }],
  certifications: [{ name: "Python Certification", issuer: "DigiDARA AI Certification", date: "2026-09-05", score: 85 }],
  achievements: [{ title: "Solved 20 Python coding problems", description: "DigiDARA Coding Practice" }],
  sources: ["Coding", "Projects", "Certification"],
  missing: ["phone", "location", "education", "linkedin", "github"],
};

function learner(): LearnerSummary {
  return {
    profile: { target_role: "data analyst", degree: "B.Sc Computer Science", skills: ["SQL", "Python"], experience: "fresher", onboarding_completed: true, onboarding_completed_at: null },
    levels: [], level_choices: [], consent_required: false, membership: null,
  };
}

beforeEach(() => { setLearnerContext(learner()); jest.mocked(api.fetchResumeFacts).mockResolvedValue(FACTS); });
afterEach(() => { setLearnerContext(null); jest.clearAllMocks(); });

test("the draft holds only facts the agents reported", () => {
  const draft = draftFromResumeFacts(FACTS);
  expect(draft.title).toBe("Data Analyst Resume");
  expect(draft.skills).toEqual(["SQL", "Python", "Power BI"]);
  expect(draft.projects).toEqual([{ title: "Sales Dashboard", description: "Tracks monthly sales. Technologies: Power BI, sql." }]);
  expect(draft.certifications?.[0]).toMatchObject({ name: "Python Certification", issue_date: "2026-09-05" });
  expect(draft.achievements?.[0]).toMatchObject({ title: "Solved 20 Python coding problems", organization: "DigiDARA" });
});

test("the opening offers the profile build first", async () => {
  const { messages } = await openResumeBuilderChat(user);
  expect(messages[0].options?.[0].value).toBe("from_profile");
});

test("it shows what it found, then asks only the missing details in order", async () => {
  const { state } = await openResumeBuilderChat(user);
  const start = await handleResumeBuilderText(state, user, "from_profile");
  expect(start.messages[0].text).toContain("Sales Dashboard");
  expect(start.messages[0].text).toContain("I only need 5 more details");
  expect(start.state.step).toBe("awaiting_phone");

  const phone = await handleResumeBuilderText(start.state, user, "9876543210");
  expect(phone.state.step).toBe("awaiting_location");

  // The normal flow would ask the target role next; the profile already has it.
  const location = await handleResumeBuilderText(phone.state, user, "Chennai, India");
  expect(location.state.step).toBe("awaiting_education");
  expect(location.messages[location.messages.length - 1].text).toContain("B.Sc Computer Science");
  expect(location.state.draft?.skills).toEqual(["SQL", "Python", "Power BI"]);

  let turn = await handleResumeBuilderText(location.state, user, "UG: B.Sc Computer Science, KSR College, 2021-2024, CGPA: 8.2");
  // An "add another?" question about education stays on education.
  if (turn.state.step === "awaiting_education_more") turn = await handleResumeBuilderText(turn.state, user, "skip");
  expect(turn.state.step).toBe("awaiting_linkedin");
  turn = await handleResumeBuilderText(turn.state, user, "skip");
  expect(turn.state.step).toBe("awaiting_github");
  turn = await handleResumeBuilderText(turn.state, user, "skip");
  expect(turn.state.step).toBe("confirming");
  expect(turn.state.draft?.education?.[0]).toMatchObject({ school: "KSR College" });
  expect(turn.messages[turn.messages.length - 1].text).toContain("Please review your details");
});
