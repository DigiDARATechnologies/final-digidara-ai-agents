import React from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import History from "../components/History";

const apiMocks = vi.hoisted(() => ({
  getHistory: vi.fn(),
  getHistoryDetail: vi.fn(),
}));

vi.mock("../api", () => apiMocks);
vi.mock("../utils/clientLogger", () => ({ reportClientError: vi.fn() }));

function LocationProbe() {
  const location = useLocation();
  return <output aria-label="Current route">{location.pathname}</output>;
}

function HistoryRoutes() {
  return (
    <>
      <Routes>
        <Route path="/history" element={<History studentId={1} />} />
        <Route path="/history/:interviewId" element={<History studentId={1} />} />
      </Routes>
      <LocationProbe />
    </>
  );
}

describe("history detail navigation", () => {
  beforeEach(() => {
    apiMocks.getHistory.mockResolvedValue({
      items: [{
        id: 54,
        student_id: 1,
        student_name: "Test Student",
        role_name: "Data Scientist",
        job_role: "Data Scientist",
        subject: "Python",
        round_type: "technical",
        difficulty: "beginner",
        status: "completed",
        overall_score: 8,
        started_at: "2026-08-04T10:00:00Z",
      }],
      pagination: {
        page: 1,
        limit: 10,
        total_items: 1,
        total_pages: 1,
        has_more: false,
      },
    });
    apiMocks.getHistoryDetail.mockResolvedValue({
      interview: {
        id: 54,
        subject: "Python",
        round_type: "technical",
        difficulty: "beginner",
        status: "completed",
        overall_score: 8,
      },
      scorecard: [],
      total_marks: 0,
      max_marks: 0,
      focus_loss_count: 0,
      focus_loss_total_seconds: 0,
      integrity_flagged: false,
    });
  });

  it("returns from an interview detail to the history list", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter
        initialEntries={["/history"]}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <HistoryRoutes />
      </MemoryRouter>
    );

    await user.click(await screen.findByRole("button", { name: "View Result" }));
    expect(await screen.findByRole("button", { name: "Back to History" }))
      .toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Current route" }))
      .toHaveTextContent("/history/54");

    await user.click(screen.getByRole("button", { name: "Back to History" }));

    expect(await screen.findByRole("heading", { name: "Interview History" }))
      .toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Current route" }))
      .toHaveTextContent("/history");
    expect(screen.queryByRole("button", { name: "Back to History" }))
      .not.toBeInTheDocument();
  });

  it("shows the interview-specific selected role instead of the subject", async () => {
    render(
      <MemoryRouter initialEntries={["/history"]}>
        <HistoryRoutes />
      </MemoryRouter>
    );

    const roles = await screen.findAllByText("Data Scientist");
    expect(roles).toHaveLength(2);
    expect(screen.queryByText("Python")).not.toBeInTheDocument();
  });
});
