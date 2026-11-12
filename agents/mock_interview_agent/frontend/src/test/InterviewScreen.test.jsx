import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import InterviewScreen from "../components/InterviewScreen";

const apiMocks = vi.hoisted(() => ({
  submitAnswer: vi.fn(),
  transcribeAudio: vi.fn(),
  endInterview: vi.fn(),
  exitInterview: vi.fn(),
  recordFocusEvent: vi.fn(),
}));
const speechMocks = vi.hoisted(() => ({
  speak: vi.fn(),
  listen: vi.fn(),
  stopListening: vi.fn(),
  finishListening: vi.fn(),
  stopSpeaking: vi.fn(),
  isSupported: false,
}));

vi.mock("../api", () => apiMocks);
vi.mock("../utils/clientLogger", () => ({
  logClientEvent: vi.fn(),
  reportClientError: vi.fn(),
  reportClientWarning: vi.fn(),
}));
vi.mock("../useSpeech", async () => {
  const actual = await vi.importActual("../useSpeech");
  return {
    ...actual,
    default: () => ({
      ...speechMocks,
      isListening: false,
      isSpeaking: false,
      isCandidateSpeaking: false,
      isSpeechRecognitionSupported: speechMocks.isSupported,
    }),
  };
});

describe("interview answer submission", () => {
  beforeEach(() => {
    speechMocks.isSupported = false;
    speechMocks.speak.mockResolvedValue(undefined);
    apiMocks.transcribeAudio.mockResolvedValue("");
    apiMocks.submitAnswer.mockResolvedValue({
      done: false,
      question: "What does a Python tuple guarantee?",
      question_order: 2,
      is_followup: false,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders a badge for a frequently asked question without changing its text", async () => {
    render(
      <InterviewScreen
        interviewId={42}
        firstQuestion="What is a Python list?"
        initialIsFrequentlyAsked
        difficulty="beginner"
        totalQuestions={5}
        onFinished={vi.fn()}
        onExited={vi.fn()}
      />
    );

    expect(await screen.findByText("⭐ Frequently asked")).toBeInTheDocument();
    expect(screen.getByText("What is a Python list?")).toBeInTheDocument();
  });

  it("transcribes recorded audio when Web Speech only detects the done phrase", async () => {
    speechMocks.isSupported = true;
    speechMocks.listen.mockResolvedValue("");
    apiMocks.transcribeAudio.mockResolvedValue(
      "A list is an ordered mutable collection. I am done."
    );
    apiMocks.submitAnswer.mockImplementation(() => new Promise(() => { }));

    const track = { stop: vi.fn() };
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [track] }) },
    });

    class FakeMediaRecorder {
      constructor(stream) {
        this.stream = stream;
        this.state = "inactive";
        this.ondataavailable = null;
        this.onstop = null;
      }

      start() {
        this.state = "recording";
      }

      stop() {
        if (this.state !== "recording") return;
        this.state = "inactive";
        this.ondataavailable?.({ data: new Blob(["recorded-answer"], { type: "audio/webm" }) });
        this.onstop?.();
      }
    }

    vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn().mockReturnValue("blob:recorded-answer"),
    });

    render(
      <InterviewScreen
        interviewId={42}
        firstQuestion="What is a Python list?"
        difficulty="beginner"
        totalQuestions={5}
        onFinished={vi.fn()}
        onExited={vi.fn()}
      />
    );

    await waitFor(() => expect(apiMocks.transcribeAudio).toHaveBeenCalledTimes(1));
    expect(apiMocks.transcribeAudio).toHaveBeenCalledWith(
      expect.any(Blob),
      expect.objectContaining({
        interviewId: 42,
        questionOrder: 1,
        signal: expect.any(AbortSignal),
      })
    );
    await waitFor(() => expect(apiMocks.submitAnswer).toHaveBeenCalledTimes(1));
    expect(apiMocks.submitAnswer).toHaveBeenCalledWith(
      expect.objectContaining({
        interview_id: 42,
        question_order: 1,
        answer: "A list is an ordered mutable collection",
        timed_out: false,
      }),
      expect.any(Object)
    );
    expect(
      screen.queryByText("Could not hear an answer. Resume when you are ready to try again.")
    ).not.toBeInTheDocument();
  });

  it("submits a typed fallback answer and advances the question UI", async () => {
    const user = userEvent.setup();
    render(
      <InterviewScreen
        interviewId={42}
        firstQuestion="What is a Python list?"
        difficulty="beginner"
        totalQuestions={5}
        onFinished={vi.fn()}
        onExited={vi.fn()}
      />
    );

    await act(async () => {
      await Promise.resolve();
    });
    const answerInput = screen.getByRole("textbox", { name: "Type your answer" });
    await user.type(answerInput, "A list is an ordered mutable collection.");
    await user.click(screen.getByRole("button", { name: "Submit Answer" }));

    await waitFor(() => {
      expect(apiMocks.submitAnswer).toHaveBeenCalledTimes(1);
    });
    expect(apiMocks.submitAnswer).toHaveBeenCalledWith(
      expect.objectContaining({
        interview_id: 42,
        question_order: 1,
        answer: "A list is an ordered mutable collection.",
        timed_out: false,
        time_taken_sec: expect.any(Number),
      }),
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
    expect(
      await screen.findByText("What does a Python tuple guarantee?")
    ).toBeInTheDocument();
    expect(screen.getAllByText("Question 2 of 5")).toHaveLength(2);
    expect(apiMocks.transcribeAudio).not.toHaveBeenCalled();
    expect(apiMocks.endInterview).not.toHaveBeenCalled();
  });

  it("automatically submits a typed manual answer when the timer expires", async () => {
    vi.useFakeTimers();
    render(
      <InterviewScreen
        interviewId={42}
        firstQuestion="What is a Python list?"
        difficulty="beginner"
        totalQuestions={5}
        onFinished={vi.fn()}
        onExited={vi.fn()}
      />
    );

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(1);
    });
    const answerInput = screen.getByRole("textbox", { name: "Type your answer" });
    fireEvent.change(answerInput, { target: { value: "A timed manual answer." } });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
      await vi.advanceTimersByTimeAsync(1);
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(apiMocks.submitAnswer).toHaveBeenCalledTimes(1);
    expect(apiMocks.submitAnswer).toHaveBeenCalledWith(
      expect.objectContaining({ answer: "A timed manual answer.", timed_out: false }),
      expect.any(Object)
    );
  });

  it("submits an empty manual answer as timed out when the timer expires", async () => {
    vi.useFakeTimers();
    render(
      <InterviewScreen
        interviewId={42}
        firstQuestion="What is a Python list?"
        difficulty="beginner"
        totalQuestions={5}
        onFinished={vi.fn()}
        onExited={vi.fn()}
      />
    );

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(1);
    });
    screen.getByRole("textbox", { name: "Type your answer" });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
      await vi.advanceTimersByTimeAsync(1);
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(apiMocks.submitAnswer).toHaveBeenCalledTimes(1);
    expect(apiMocks.submitAnswer).toHaveBeenCalledWith(
      expect.objectContaining({ answer: "", timed_out: true }),
      expect.any(Object)
    );
  });

  it("aborts an in-flight submission when exit is confirmed", async () => {
    const user = userEvent.setup();
    apiMocks.submitAnswer.mockImplementation(() => new Promise(() => { }));
    render(
      <InterviewScreen
        interviewId={42}
        firstQuestion="What is a Python list?"
        difficulty="beginner"
        totalQuestions={5}
        onFinished={vi.fn()}
        onExited={vi.fn()}
      />
    );

    const answerInput = await screen.findByRole("textbox", { name: "Type your answer" });
    await user.type(answerInput, "An answer that is being submitted.");
    await user.click(screen.getByRole("button", { name: "Submit Answer" }));
    await waitFor(() => expect(apiMocks.submitAnswer).toHaveBeenCalledTimes(1));

    const signal = apiMocks.submitAnswer.mock.calls[0][1].signal;
    expect(signal.aborted).toBe(false);
    await user.click(screen.getByRole("button", { name: "Exit interview" }));
    await user.click(screen.getByRole("button", { name: /^Exit Interview$/ }));
    expect(signal.aborted).toBe(true);
  });

  it("prevents duplicate manual submissions while a request is pending", async () => {
    apiMocks.submitAnswer.mockImplementation(() => new Promise(() => {}));
    render(
      <InterviewScreen
        interviewId={42}
        firstQuestion="What is a Python list?"
        difficulty="beginner"
        totalQuestions={5}
        onFinished={vi.fn()}
        onExited={vi.fn()}
      />
    );

    const answerInput = await screen.findByRole("textbox", { name: "Type your answer" });
    fireEvent.change(answerInput, { target: { value: "Submit this answer only once." } });
    const submitButton = screen.getByRole("button", { name: "Submit Answer" });
    fireEvent.click(submitButton);
    fireEvent.click(submitButton);

    await waitFor(() => expect(apiMocks.submitAnswer).toHaveBeenCalledTimes(1));
  });

  it("retries a failed submission with the same answer", async () => {
    const user = userEvent.setup();
    apiMocks.submitAnswer
      .mockRejectedValueOnce(new Error("temporary failure"))
      .mockResolvedValueOnce({
        done: false,
        question: "What does a Python tuple guarantee?",
        question_order: 2,
        is_followup: false,
      });
    render(
      <InterviewScreen
        interviewId={42}
        firstQuestion="What is a Python list?"
        difficulty="beginner"
        totalQuestions={5}
        onFinished={vi.fn()}
        onExited={vi.fn()}
      />
    );

    const answer = "A retryable answer.";
    const answerInput = await screen.findByRole("textbox", { name: "Type your answer" });
    await user.type(answerInput, answer);
    await user.click(screen.getByRole("button", { name: "Submit Answer" }));
    await screen.findByText("temporary failure");
    await user.click(screen.getByRole("button", { name: "Try submitting again" }));

    await waitFor(() => expect(apiMocks.submitAnswer).toHaveBeenCalledTimes(2));
    expect(apiMocks.submitAnswer.mock.calls[1][0]).toEqual(
      expect.objectContaining({ answer })
    );
    expect(await screen.findByText("What does a Python tuple guarantee?")).toBeInTheDocument();
  });
});
