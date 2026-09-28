import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import ResumeBuilderDashboard from "../../src/components/ResumeBuilderDashboard";
import * as resumeApi from "../../src/lib/resumeBuilderApi";

jest.mock("../../src/lib/resumeBuilderApi", () => ({
  exportResumePdf: jest.fn(),
  getResume: jest.fn(),
  listResumeTemplates: jest.fn(),
  previewResumePdf: jest.fn(),
  selectResumeTemplate: jest.fn(),
}));

const api = resumeApi as jest.Mocked<typeof resumeApi>;
const user = { id: "learner", name: "Rubeshkanna", email: "rubesh@example.test", mobile: "", initial: "R" };
const state = { step: "completed" as const, resumeId: 7, resumeTitle: "Data Analyst", atsScore: 93, templateChoice: "pulse-rose" };

beforeEach(() => {
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: jest.fn(() => "blob:resume-preview") });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: jest.fn() });
  api.listResumeTemplates.mockResolvedValue([
    { id: "pulse-rose", name: "Pulse Rose" },
    { id: "slate-dawn", name: "Executive Slate" },
  ]);
  api.getResume.mockResolvedValue({
    id: 7, user_id: "learner", target_role: "Data Analyst", template_choice: "pulse-rose",
    personal_info: { name: "Rubeshkanna", email: "rubesh@example.test" }, summary: "Target-role summary.",
  });
  api.previewResumePdf.mockResolvedValue(new Blob(["%PDF-1.4"]));
  api.selectResumeTemplate.mockResolvedValue({});
});

test("renders the saved final resume as a selected-template preview and refreshes it on template change", async () => {
  render(<ResumeBuilderDashboard user={user} state={state} onClose={jest.fn()} />);

  await waitFor(() => expect(screen.getByTitle("Resume PDF preview")).toBeInTheDocument());
  expect(api.previewResumePdf).toHaveBeenCalledWith(
    "learner", expect.objectContaining({ summary: "Target-role summary.", target_role: "Data Analyst" }), "pulse-rose",
  );

  fireEvent.change(screen.getByRole("combobox"), { target: { value: "slate-dawn" } });
  await waitFor(() => expect(api.previewResumePdf).toHaveBeenLastCalledWith(
    "learner", expect.objectContaining({ summary: "Target-role summary.", template_choice: "slate-dawn" }), "slate-dawn",
  ));
});
