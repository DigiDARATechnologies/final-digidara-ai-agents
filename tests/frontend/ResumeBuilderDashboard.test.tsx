import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import ResumeBuilderDashboard from "../../src/components/ResumeBuilderDashboard";
import * as resumeApi from "../../src/lib/resumeBuilderApi";

jest.mock("../../src/lib/resumeBuilderApi", () => ({
  DEFAULT_RESUME_STYLE: { font_family: "template", font_scale: 1, line_spacing: 1 },
  exportResumePdf: jest.fn(),
  getResume: jest.fn(),
  listResumeStyles: jest.fn(),
  listResumeTemplates: jest.fn(),
  previewResumePdf: jest.fn(),
  saveResumeStyle: jest.fn(),
  selectResumeTemplate: jest.fn(),
  suggestResumeStyle: jest.fn(),
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
  api.listResumeStyles.mockRejectedValue(new Error("offline")); // the built-in list is used
  api.saveResumeStyle.mockResolvedValue({});
});

const templateStyle = { font_family: "template", font_scale: 1, line_spacing: 1 };

test("renders the saved final resume as a selected-template preview and refreshes it on template change", async () => {
  render(<ResumeBuilderDashboard user={user} state={state} onClose={jest.fn()} />);

  await waitFor(() => expect(screen.getByTitle("Resume PDF preview")).toBeInTheDocument());
  expect(api.previewResumePdf).toHaveBeenCalledWith(
    "learner", expect.objectContaining({ summary: "Target-role summary.", target_role: "Data Analyst" }), "pulse-rose", templateStyle,
  );

  fireEvent.change(screen.getAllByRole("combobox")[0], { target: { value: "slate-dawn" } });
  await waitFor(() => expect(api.previewResumePdf).toHaveBeenLastCalledWith(
    "learner", expect.objectContaining({ summary: "Target-role summary.", template_choice: "slate-dawn" }), "slate-dawn", templateStyle,
  ));
});

test("changing the font, size or spacing saves it and refreshes the preview", async () => {
  render(<ResumeBuilderDashboard user={user} state={state} onClose={jest.fn()} />);
  await waitFor(() => expect(screen.getByLabelText("Font")).toBeInTheDocument());

  fireEvent.change(screen.getByLabelText("Font"), { target: { value: "carlito" } });
  const carlito = { font_family: "carlito", font_scale: 1, line_spacing: 1 };
  await waitFor(() => expect(api.saveResumeStyle).toHaveBeenCalledWith("learner", 7, carlito));
  await waitFor(() => expect(api.previewResumePdf).toHaveBeenLastCalledWith("learner", expect.any(Object), "pulse-rose", carlito));

  fireEvent.change(screen.getByLabelText("Font size"), { target: { value: "1.1" } });
  fireEvent.change(screen.getByLabelText("Line spacing"), { target: { value: "1.15" } });
  await waitFor(() => expect(api.saveResumeStyle).toHaveBeenLastCalledWith("learner", 7, { font_family: "carlito", font_scale: 1.1, line_spacing: 1.15 }));
});

test("a saved style is shown and used when the dashboard opens", async () => {
  api.getResume.mockResolvedValue({ id: 7, template_choice: "pulse-rose", style_settings: { font_family: "lato", font_scale: 0.95, line_spacing: 1 } });
  render(<ResumeBuilderDashboard user={user} state={state} onClose={jest.fn()} />);
  await waitFor(() => expect(screen.getByLabelText("Font")).toHaveValue("lato"));
  await waitFor(() => expect(api.previewResumePdf).toHaveBeenLastCalledWith("learner", expect.any(Object), "pulse-rose", { font_family: "lato", font_scale: 0.95, line_spacing: 1 }));
});

test("the AI style suggestion can be applied, or ignored with Keep mine", async () => {
  api.suggestResumeStyle.mockResolvedValue({ style: { font_family: "carlito", font_scale: 1, line_spacing: 1 }, reason: "Carlito is clean and ATS-friendly.", source: "ai" });
  render(<ResumeBuilderDashboard user={user} state={state} onClose={jest.fn()} />);
  await waitFor(() => expect(screen.getByLabelText("Font")).toBeInTheDocument());

  fireEvent.click(screen.getByRole("button", { name: /Suggest a professional style/ }));
  expect(await screen.findByText("Carlito is clean and ATS-friendly.")).toBeInTheDocument();
  expect(screen.getByText(/Carlito \(Calibri style\) · 100% size · Standard spacing/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Keep mine" }));
  expect(screen.queryByText("Carlito is clean and ATS-friendly.")).not.toBeInTheDocument();
  expect(api.saveResumeStyle).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole("button", { name: /Suggest a professional style/ }));
  fireEvent.click(await screen.findByRole("button", { name: "Apply this style" }));
  await waitFor(() => expect(api.saveResumeStyle).toHaveBeenCalledWith("learner", 7, { font_family: "carlito", font_scale: 1, line_spacing: 1 }));
  expect(screen.getByLabelText("Font")).toHaveValue("carlito");
});

test("a style that cannot be saved is undone and explained", async () => {
  api.saveResumeStyle.mockRejectedValue(new Error("Unknown font_family"));
  render(<ResumeBuilderDashboard user={user} state={state} onClose={jest.fn()} />);
  await waitFor(() => expect(screen.getByLabelText("Font")).toBeInTheDocument());
  fireEvent.change(screen.getByLabelText("Font"), { target: { value: "lato" } });
  expect(await screen.findByRole("alert")).toHaveTextContent("That style could not be saved: Unknown font_family");
  expect(screen.getByLabelText("Font")).toHaveValue("template");
});

test("the download uses the chosen style", async () => {
  api.exportResumePdf.mockResolvedValue({ blob: new Blob(["%PDF"]), filename: "resume.pdf" });
  render(<ResumeBuilderDashboard user={user} state={state} onClose={jest.fn()} />);
  await waitFor(() => expect(screen.getByLabelText("Font")).toBeInTheDocument());
  fireEvent.change(screen.getByLabelText("Font"), { target: { value: "open-sans" } });
  await waitFor(() => expect(api.saveResumeStyle).toHaveBeenCalled());
  fireEvent.click(screen.getByRole("button", { name: "Download PDF" }));
  await waitFor(() => expect(api.exportResumePdf).toHaveBeenCalledWith("learner", 7, "pulse-rose", { font_family: "open-sans", font_scale: 1, line_spacing: 1 }));
});
