import { fireEvent, render, screen, within } from "@testing-library/react";
import JobsAdminPanel from "../../src/components/admin/JobsAdminPanel";

jest.mock("../../src/lib/jobFetchApi", () => ({
  adminListJobs: jest.fn().mockResolvedValue({ jobs: [
    { id: 1, title: "Adzuna role", company: "Example", external_id: "legacy-id-a", source_type: "adzuna", status: "active" },
    { id: 2, title: "JSearch role", company: "Example", external_id: "legacy-id-b", source_type: "jsearch", status: "active" },
    { id: 3, title: "Manual role", company: "Example", external_id: "manual:1", source_type: null, status: "active" },
  ] }),
  adminListCategories: jest.fn().mockResolvedValue({ categories: [] }),
  adminGetAutomation: jest.fn().mockResolvedValue({ automation: null, free_plan: {
    usage: { adzuna: [{ window: "month", used: 312, limit: 2500 }], jsearch: [{ window: "month", used: 40, limit: 200 }] },
    upcoming: [{ date: "2026-10-02", adzuna: [{ city: "Chennai", roles: ["Java Developer", "React Developer"] }], jsearch: ["QA Engineer fresher in Tamil Nadu"] }],
  } }),
  adminListSources: jest.fn().mockResolvedValue({ sources: [] }),
  adminApifyActors: jest.fn().mockResolvedValue({ actors: [] }),
  adminListRuns: jest.fn().mockResolvedValue({ runs: [] }),
  adminListUsers: jest.fn().mockResolvedValue({ users: [
    { user_id: "4b8045260dbe4129856ae74c6aeeb784", plan_tier: "free", profile_completed: 1, created_at: "2026-10-01T09:00:00" },
    { user_id: "unknown-id", plan_tier: "pro", profile_completed: 0, created_at: null },
  ] }),
}));
jest.mock("../../src/lib/adminApi", () => ({
  fetchUsers: jest.fn().mockResolvedValue({ total: 1, page: 1, limit: 100, users: [
    { id: "4b8045260dbe4129856ae74c6aeeb784", name: "Rubesh Kanna", email: "rubesh@example.com", plan_name: "Standard" },
  ] }),
}));

test("admin source badges and filter use stored provider metadata and tolerate a missing source", async () => {
  render(<JobsAdminPanel />);
  const adzuna = await screen.findByText("Adzuna role");
  const jsearch = screen.getByText("JSearch role");
  const manual = screen.getByText("Manual role");
  expect(within(adzuna.closest("tr")!).getByText("Adzuna")).toBeInTheDocument();
  expect(within(jsearch.closest("tr")!).getByText("RapidAPI JSearch")).toBeInTheDocument();
  expect(within(manual.closest("tr")!).getByText("Manual")).toBeInTheDocument();
  fireEvent.change(screen.getByDisplayValue("All Sources"), { target: { value: "jsearch" } });
  expect(screen.getByText("JSearch role")).toBeInTheDocument();
  expect(screen.queryByText("Adzuna role")).not.toBeInTheDocument();
  expect(screen.queryByText("Manual role")).not.toBeInTheDocument();
});

test("users & plans names each user and shows their billing plan beside the job feed tier", async () => {
  render(<JobsAdminPanel />);
  fireEvent.click(await screen.findByRole("button", { name: "Users & plans" }));
  const rubesh = await screen.findByText("Rubesh Kanna");
  const row = within(rubesh.closest("tr")!);
  expect(row.getByText("rubesh@example.com")).toBeInTheDocument();
  expect(row.getByText("Standard")).toBeInTheDocument();
  expect(row.getByText("free")).toBeInTheDocument();
  expect(screen.queryByText("4b8045260dbe4129856ae74c6aeeb784")).not.toBeInTheDocument();
  // An id the platform list does not know still shows, rather than vanishing.
  expect(screen.getByText("unknown-id")).toBeInTheDocument();
});

test("sources tab shows free-plan usage and the next days' role and city plan", async () => {
  render(<JobsAdminPanel />);
  fireEvent.click(await screen.findByRole("button", { name: /Sources & Automation/ }));
  expect(await screen.findByText("Free plan: API calls used")).toBeInTheDocument();
  expect(screen.getByText("month: 312 / 2,500")).toBeInTheDocument();
  expect(screen.getByText("month: 40 / 200")).toBeInTheDocument();
  expect(screen.getByText(/2 Adzuna \+ 1 JSearch searches/)).toBeInTheDocument();
  expect(screen.getByText("Java Developer, React Developer")).toBeInTheDocument();
});
