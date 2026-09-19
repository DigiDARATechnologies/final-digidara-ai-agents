import React from "react";
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import useInterviewFocusTracking from "../useInterviewFocusTracking";

const apiMocks = vi.hoisted(() => ({ recordFocusEvent: vi.fn() }));

vi.mock("../api", () => apiMocks);
vi.mock("../utils/clientLogger", () => ({ reportClientWarning: vi.fn() }));

function TrackingHarness({ active = true }) {
  const { warning, summary } = useInterviewFocusTracking(42, active);
  return (
    <div>
      <span data-testid="warning">{warning}</span>
      <span data-testid="count">{summary.focus_loss_count}</span>
    </div>
  );
}

describe("interview focus-loss tracking", () => {
  let visibilityState;
  let focused;

  beforeEach(() => {
    vi.useFakeTimers();
    visibilityState = "visible";
    focused = true;
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => visibilityState,
    });
    vi.spyOn(document, "hasFocus").mockImplementation(() => focused);
    apiMocks.recordFocusEvent
      .mockResolvedValueOnce({
        focus_loss_count: 1,
        focus_loss_total_seconds: 0,
        integrity_flagged: false,
      })
      .mockResolvedValueOnce({
        away_seconds: 12,
        focus_loss_count: 1,
        focus_loss_total_seconds: 12,
        integrity_flagged: false,
      });
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it("deduplicates visibility and blur signals and warns after return", async () => {
    render(<TrackingHarness />);

    visibilityState = "hidden";
    focused = false;
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
      window.dispatchEvent(new Event("blur"));
      await Promise.resolve();
    });

    expect(apiMocks.recordFocusEvent).toHaveBeenCalledTimes(1);
    expect(apiMocks.recordFocusEvent).toHaveBeenCalledWith(
      42,
      expect.objectContaining({ action: "left", source: "visibility" })
    );

    visibilityState = "visible";
    focused = true;
    await act(async () => {
      window.dispatchEvent(new Event("focus"));
      await Promise.resolve();
    });

    expect(apiMocks.recordFocusEvent).toHaveBeenCalledTimes(2);
    expect(apiMocks.recordFocusEvent).toHaveBeenLastCalledWith(
      42,
      expect.objectContaining({ action: "returned" })
    );
    expect(
      screen.getByText(
        "You left the interview window for 12 seconds. This has been recorded, but your interview will continue normally."
      )
    ).toBeInTheDocument();
    expect(screen.getByTestId("count")).toHaveTextContent("1");
  });

  it("ignores a brief blur that returns inside the grace period", () => {
    render(<TrackingHarness />);

    focused = false;
    act(() => {
      window.dispatchEvent(new Event("blur"));
      vi.advanceTimersByTime(500);
      focused = true;
      window.dispatchEvent(new Event("focus"));
      vi.advanceTimersByTime(600);
    });

    expect(apiMocks.recordFocusEvent).not.toHaveBeenCalled();
  });

  it("does not track outside an active interview", () => {
    render(<TrackingHarness active={false} />);
    visibilityState = "hidden";
    focused = false;
    act(() => {
      document.dispatchEvent(new Event("visibilitychange"));
      window.dispatchEvent(new Event("blur"));
      vi.advanceTimersByTime(1500);
    });
    expect(apiMocks.recordFocusEvent).not.toHaveBeenCalled();
  });

  it("never claims an event was recorded when persistence fails", async () => {
    apiMocks.recordFocusEvent.mockReset();
    apiMocks.recordFocusEvent.mockRejectedValue(new Error("Route unavailable"));
    render(<TrackingHarness />);

    visibilityState = "hidden";
    focused = false;
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
      await Promise.resolve();
    });

    visibilityState = "visible";
    focused = true;
    await act(async () => {
      window.dispatchEvent(new Event("focus"));
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getByTestId("warning")).toHaveTextContent(
      "Focus loss was detected, but it could not be saved. Your interview will continue normally."
    );
    expect(screen.getByTestId("warning")).not.toHaveTextContent(
      "This has been recorded"
    );
  });
});
