import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SetupScreen from "../components/SetupScreen";

const apiMocks = vi.hoisted(() => ({
  getDailyUsage: vi.fn(),
  startInterview: vi.fn(),
}));

vi.mock("../api", () => apiMocks);

describe("technical interview entry points", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.getDailyUsage.mockResolvedValue({
      daily_limit_enabled: false,
      daily_remaining: null,
    });
    apiMocks.startInterview.mockResolvedValue({
      interview_id: 42,
      question: "Generated question?",
      total_questions: 5,
    });
  });

  it("shows only role-based and custom-topic technical options", () => {
    render(<SetupScreen studentId={1} onStarted={vi.fn()} />);

    expect(screen.getByRole("button", { name: /Role-Based/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Custom Topics/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Course-Based/i })).not.toBeInTheDocument();
    expect(screen.queryByText("Preset Subject")).not.toBeInTheDocument();
  });

  it("starts a role-based technical interview", async () => {
    const user = userEvent.setup();
    render(<SetupScreen studentId={1} onStarted={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Data Analyst" }));
    await user.click(screen.getByRole("button", { name: "Start Interview" }));

    await waitFor(() => expect(apiMocks.startInterview).toHaveBeenCalledWith(
      expect.objectContaining({
        interview_mode: "role",
        role_name: "Data Analyst",
        round_type: "technical",
        subject: null,
      })
    ));
  });

  it("allows selecting five or fifteen questions and sends the selected count", async () => {
    const user = userEvent.setup();
    render(<SetupScreen studentId={1} onStarted={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /^55 Questions/i }));
    await user.click(screen.getByRole("button", { name: "Start Interview" }));
    await waitFor(() => expect(apiMocks.startInterview).toHaveBeenCalledWith(
      expect.objectContaining({ num_questions: 5 })
    ));

    apiMocks.startInterview.mockClear();
    await user.click(screen.getByRole("button", { name: /15 Questions/i }));
    await user.click(screen.getByRole("button", { name: "Start Interview" }));
    await waitFor(() => expect(apiMocks.startInterview).toHaveBeenCalledWith(
      expect.objectContaining({ num_questions: 15 })
    ));
  });

  it("keeps the HR interview flow unchanged", async () => {
    const user = userEvent.setup();
    render(<SetupScreen studentId={1} onStarted={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /HR Interview/i }));
    expect(screen.queryByRole("button", { name: /Role-Based/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Custom Topics/i })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Start Interview" }));
    await waitFor(() => expect(apiMocks.startInterview).toHaveBeenCalledWith(
      expect.objectContaining({
        interview_mode: "course",
        round_type: "hr",
        role_name: null,
        subject: null,
      })
    ));
  });
});
