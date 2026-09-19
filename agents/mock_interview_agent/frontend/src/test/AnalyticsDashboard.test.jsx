import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AnalyticsDashboard from "../components/AnalyticsDashboard";

const apiMocks = vi.hoisted(() => ({
  getAnalyticsSummary: vi.fn(), getAnalyticsDaily: vi.fn(), getAnalyticsMonthly: vi.fn(),
  getAnalyticsTokenBreakdown: vi.fn(), getAnalyticsInterviews: vi.fn(),
  getAnalyticsQuestions: vi.fn(), getAnalyticsRecent: vi.fn(),
}));

vi.mock("../api", () => apiMocks);
vi.mock("../utils/clientLogger", () => ({ reportClientError: vi.fn() }));

const emptyPage = { items: [], pagination: {} };

describe("AI usage analytics dashboard", () => {
  beforeEach(() => {
    apiMocks.getAnalyticsSummary.mockResolvedValue({ range: { start_date: "2026-08-01", end_date: "2026-08-07" }, summary: { total_interviews: 0, total_requests: 0, total_tokens: 0, estimated_cost: 0 }, today: { tokens: 0, estimated_cost: 0, interviews: 0 } });
    apiMocks.getAnalyticsDaily.mockResolvedValue({ items: [] });
    apiMocks.getAnalyticsMonthly.mockResolvedValue({ items: [] });
    apiMocks.getAnalyticsTokenBreakdown.mockResolvedValue({ prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 });
    apiMocks.getAnalyticsInterviews.mockResolvedValue(emptyPage);
    apiMocks.getAnalyticsQuestions.mockResolvedValue(emptyPage);
    apiMocks.getAnalyticsRecent.mockResolvedValue(emptyPage);
  });

  it("renders a safe empty state when the student has no AI usage", async () => {
    render(<AnalyticsDashboard studentId={1} />);
    expect(await screen.findByText("No AI usage yet")).toBeInTheDocument();
    expect(screen.getByText(/Complete an interview to see provider-reported token usage/)).toBeInTheDocument();
    expect(apiMocks.getAnalyticsSummary).toHaveBeenCalledWith(1, {});
  });

  it("applies the selected date range to analytics requests", async () => {
    const summary1 = {
      range: { start_date: "2026-08-01", end_date: "2026-08-07" },
      summary: { total_interviews: 0, total_requests: 0, total_tokens: 0, estimated_cost: 0 },
      today: { tokens: 0, estimated_cost: 0, interviews: 0 },
    };
    const summary2 = {
      range: { start_date: "2026-08-07", end_date: "2026-08-08" },
      summary: { total_interviews: 1, total_requests: 10, total_tokens: 5000, estimated_cost: 0.002 },
      today: { tokens: 1000, estimated_cost: 0.0004, interviews: 1 },
    };
    apiMocks.getAnalyticsSummary
      .mockResolvedValueOnce(summary1)
      .mockResolvedValueOnce(summary2)
      .mockResolvedValueOnce(summary2);
    apiMocks.getAnalyticsDaily
      .mockResolvedValueOnce({ items: [] })
      .mockResolvedValueOnce({ items: [] })
      .mockResolvedValueOnce({ items: [] });
    apiMocks.getAnalyticsMonthly
      .mockResolvedValueOnce({ items: [] })
      .mockResolvedValueOnce({ items: [] })
      .mockResolvedValueOnce({ items: [] });
    apiMocks.getAnalyticsTokenBreakdown
      .mockResolvedValueOnce({ prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 })
      .mockResolvedValueOnce({ prompt_tokens: 4000, completion_tokens: 1000, total_tokens: 5000 })
      .mockResolvedValueOnce({ prompt_tokens: 4000, completion_tokens: 1000, total_tokens: 5000 });
    apiMocks.getAnalyticsInterviews
      .mockResolvedValueOnce(emptyPage)
      .mockResolvedValueOnce(emptyPage)
      .mockResolvedValueOnce(emptyPage);
    apiMocks.getAnalyticsQuestions
      .mockResolvedValueOnce(emptyPage)
      .mockResolvedValueOnce(emptyPage)
      .mockResolvedValueOnce(emptyPage);
    apiMocks.getAnalyticsRecent
      .mockResolvedValueOnce(emptyPage)
      .mockResolvedValueOnce(emptyPage)
      .mockResolvedValueOnce(emptyPage);

    render(<AnalyticsDashboard studentId={1} />);
    expect(await screen.findByText("No AI usage yet")).toBeInTheDocument();

    const fromInput = screen.getByLabelText("From");
    const toInput = screen.getByLabelText("To");

    fireEvent.change(fromInput, { target: { value: "2026-08-07" } });
    fireEvent.change(toInput, { target: { value: "2026-08-08" } });

    await waitFor(() => expect(apiMocks.getAnalyticsSummary).toHaveBeenLastCalledWith(1, {
      start_date: "2026-08-07",
      end_date: "2026-08-08",
    }));
  });
});
