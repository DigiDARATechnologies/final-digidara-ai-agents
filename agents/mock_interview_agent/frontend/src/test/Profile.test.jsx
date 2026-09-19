import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Profile from "../components/Profile";

const apiMocks = vi.hoisted(() => ({
  getProfile: vi.fn(),
  updateProfile: vi.fn(),
  uploadProfileAvatar: vi.fn(),
  removeProfileAvatar: vi.fn(),
}));

vi.mock("../api", () => apiMocks);
vi.mock("../utils/clientLogger", () => ({ reportClientError: vi.fn() }));

const profile = {
  id: 1,
  name: "Asha Student",
  email: "asha@example.com",
  phone: "9876543210",
  course_enrolled: "Full Stack Development",
  target_role: "Software Engineer",
  bio: "Learning every day.",
  avatar_color: "#2563eb",
  avatar_url: null,
  total_interviews: 3,
  average_score: 8,
  technical_interviews_count: 2,
  hr_interviews_count: 1,
};

async function openEditor(user) {
  await screen.findByRole("button", { name: /Edit Profile/ });
  await user.click(screen.getByRole("button", { name: /Edit Profile/ }));
}

describe("profile editing", () => {
  beforeEach(() => {
    apiMocks.getProfile.mockResolvedValue(profile);
    apiMocks.updateProfile.mockReset();
  });

  it("requires name and email before calling the update API", async () => {
    const user = userEvent.setup();
    render(<Profile studentId={1} onProfileUpdate={vi.fn()} />);
    await openEditor(user);

    const name = screen.getByRole("textbox", { name: "Name" });
    const email = screen
      .getAllByRole("textbox", { name: "Email" })
      .find((input) => input.required);
    expect(name).toBeRequired();
    expect(email).toBeRequired();

    await user.clear(name);
    await user.click(screen.getByRole("button", { name: /Save Profile/ }));

    expect(screen.getByRole("alert")).toHaveTextContent("Name and email are required.");
    expect(apiMocks.updateProfile).not.toHaveBeenCalled();
  });

  it("saves edited fields and reports the updated profile", async () => {
    const user = userEvent.setup();
    const onProfileUpdate = vi.fn();
    const updated = { ...profile, phone: "9999999999", target_role: "Backend Engineer" };
    apiMocks.updateProfile.mockResolvedValue(updated);
    render(<Profile studentId={1} onProfileUpdate={onProfileUpdate} />);
    await openEditor(user);

    const phone = screen.getByRole("textbox", { name: "Phone" });
    const targetRole = screen.getByRole("textbox", { name: "Target Role" });
    await user.clear(phone);
    await user.type(phone, updated.phone);
    await user.clear(targetRole);
    await user.type(targetRole, updated.target_role);
    await user.click(screen.getByRole("button", { name: /Save Profile/ }));

    await waitFor(() => expect(apiMocks.updateProfile).toHaveBeenCalledTimes(1));
    expect(apiMocks.updateProfile).toHaveBeenCalledWith(
      1,
      expect.objectContaining({
        name: profile.name,
        email: profile.email,
        phone: updated.phone,
        course_enrolled: profile.course_enrolled,
        target_role: updated.target_role,
      })
    );
    expect(onProfileUpdate).toHaveBeenCalledWith(updated);
    expect(await screen.findByRole("button", { name: /Edit Profile/ })).toBeInTheDocument();
    expect(screen.getAllByText("Backend Engineer").length).toBeGreaterThanOrEqual(1);
  });

  it("keeps the editor open and displays API save failures", async () => {
    const user = userEvent.setup();
    apiMocks.updateProfile.mockRejectedValue(new Error("Profile service unavailable."));
    render(<Profile studentId={1} onProfileUpdate={vi.fn()} />);
    await openEditor(user);

    await user.click(screen.getByRole("button", { name: /Save Profile/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Profile service unavailable.");
    expect(screen.getByRole("button", { name: /Save Profile/ })).toBeInTheDocument();
  });
});
