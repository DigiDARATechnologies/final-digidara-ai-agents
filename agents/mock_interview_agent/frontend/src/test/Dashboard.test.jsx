import React from "react";
import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Dashboard from "../components/Dashboard";

const apiMocks = vi.hoisted(() => ({
  getDashboard: vi.fn(),
}));

vi.mock("../api", () => apiMocks);
vi.mock("../utils/clientLogger", () => ({ reportClientError: vi.fn() }));

function deferred() {
  let resolve;
  const promise = new Promise((promiseResolve) => {
    resolve = promiseResolve;
  });
  return { promise, resolve };
}

describe("dashboard rendering", () => {
  beforeEach(() => {
    apiMocks.getDashboard.mockReset();
  });

  it("shows loading placeholders and then renders dashboard statistics", async () => {
    const request = deferred();
    apiMocks.getDashboard.mockReturnValue(request.promise);
    const { container } = render(
      <Dashboard
        studentId={1}
        studentName="Asha"
        onStartInterview={vi.fn()}
        onViewInterview={vi.fn()}
      />
    );

    expect(container.querySelector(".skeleton-hero")).toBeInTheDocument();

    await act(async () => {
      request.resolve({
        total_interviews: 4,
        average_score: 8.2,
        highest_score: 9.1,
        recent_interview_score: 8.7,
        technical_performance: 8.4,
        communication_performance: 7.9,
        weekly_practice_count: 2,
        interviews_this_month: 3,
        improvement: { status: "available", label: "+0.8", recent_count: 2 },
        recent_interviews: [],
        skill_performance_trend: [],
        weak_subjects: [],
        recommended_next_interview: null,
      });
      await request.promise;
    });

    expect(await screen.findByText("Welcome back, Asha!")).toBeInTheDocument();
    expect(screen.getByText("Completed Interviews").previousSibling).toHaveTextContent("4");
    expect(screen.getByText("Average Score").previousSibling).toHaveTextContent("8.2/10");
    expect(screen.getByText("Highest Score").previousSibling).toHaveTextContent("9.1/10");
    expect(screen.getByText("Score Improvement").previousSibling).toHaveTextContent("+0.8");
  });

  it("renders a useful empty state when no interviews are complete", async () => {
    apiMocks.getDashboard.mockResolvedValue({ total_interviews: 0 });
    render(
      <Dashboard
        studentId={1}
        studentName=""
        onStartInterview={vi.fn()}
        onViewInterview={vi.fn()}
      />
    );

    expect(
      await screen.findByText("No interviews completed yet")
    ).toBeInTheDocument();
    expect(screen.getByText(/Complete your first mock interview/)).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Start New Interview/ })).toHaveLength(2);
  });
});
