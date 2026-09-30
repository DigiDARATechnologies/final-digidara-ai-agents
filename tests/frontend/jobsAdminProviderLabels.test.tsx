import { fireEvent, render, screen, within } from "@testing-library/react";
import JobsAdminPanel from "../../src/components/admin/JobsAdminPanel";

jest.mock("../../src/lib/jobFetchApi", () => ({
  adminListJobs: jest.fn().mockResolvedValue({ jobs: [
    { id: 1, title: "Adzuna role", company: "Example", external_id: "legacy-id-a", source_type: "adzuna", status: "active" },
    { id: 2, title: "JSearch role", company: "Example", external_id: "legacy-id-b", source_type: "jsearch", status: "active" },
    { id: 3, title: "Manual role", company: "Example", external_id: "manual:1", source_type: null, status: "active" },
  ] }),
  adminListCategories: jest.fn().mockResolvedValue({ categories: [] }),
  adminGetAutomation: jest.fn().mockResolvedValue({ automation: null }),
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
