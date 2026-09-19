import React from "react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";

const apiMocks = vi.hoisted(() => ({
  getActiveInterview: vi.fn(),
  getProfile: vi.fn(),
}));

vi.mock("../api", () => apiMocks);
vi.mock("../components/Dashboard", () => ({
  default: () => <div>Dashboard page</div>,
}));
vi.mock("../components/SetupScreen", () => ({
  default: () => <div>New interview page</div>,
}));
vi.mock("../components/History", () => ({
  default: () => <div>History page</div>,
}));
vi.mock("../components/Profile", () => ({
  default: () => <div>Profile page</div>,
}));
vi.mock("../components/InterviewScreen", () => ({
  default: () => <div>Interview page</div>,
}));
vi.mock("../components/ResultScreen", () => ({
  default: () => <div>Result page</div>,
}));

function LocationProbe() {
  const location = useLocation();
  return <output aria-label="Current route">{location.pathname}</output>;
}

describe("sidebar routing", () => {
  beforeEach(() => {
    localStorage.clear();
    apiMocks.getActiveInterview.mockResolvedValue({ active: false });
    apiMocks.getProfile.mockResolvedValue({
      name: "Test Student",
      email: "student@example.com",
      avatar_color: "#2563eb",
    });
  });

  it("navigates to every sidebar route and highlights the active item", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter
        initialEntries={["/dashboard"]}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <App />
        <LocationProbe />
      </MemoryRouter>
    );

    const navigation = screen.getByRole("navigation", { name: "Main navigation" });
    const dashboard = within(navigation).getByRole("button", { name: "Dashboard" });
    expect(dashboard).toHaveClass("nav-item-active");
    expect(screen.getByText("Dashboard page")).toBeInTheDocument();

    const cases = [
      ["New Interview", "/new-interview", "New interview page"],
      ["Interview History", "/history", "History page"],
      ["Profile", "/profile", "Profile page"],
      ["Dashboard", "/dashboard", "Dashboard page"],
    ];

    for (const [label, route, pageText] of cases) {
      const item = within(navigation).getByRole("button", { name: label });
      await user.click(item);
      expect(screen.getByRole("status", { name: "Current route" })).toHaveTextContent(route);
      expect(screen.getByText(pageText)).toBeInTheDocument();
      expect(item).toHaveClass("nav-item-active");
    }
  });
});
