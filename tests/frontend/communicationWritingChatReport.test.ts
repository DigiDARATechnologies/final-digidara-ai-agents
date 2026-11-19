jest.mock("../../src/lib/communicationApi", () => ({
  finishWritingChat: jest.fn(),
  downloadWritingReportPdf: jest.fn(),
  writingChat: jest.fn(),
}));

import * as api from "../../src/lib/communicationApi";
import { handleCommunicationText, type CommunicationFlowState } from "../../src/lib/communicationFlow";

const mocked = jest.mocked(api);

const chatState = (history: CommunicationFlowState["writingChatHistory"]): CommunicationFlowState => ({
  step: "writing_chat_turn", authToken: "token", difficulty: "medium", activeModule: "writing",
  writingMode: "chat", writingTopic: "Teamwork", writingChatHistory: history,
});

afterEach(() => jest.clearAllMocks());

test("ending a writing chat saves it and offers the PDF report", async () => {
  mocked.finishWritingChat.mockResolvedValue({ session_id: 42, overall_score: 6.7, summary_feedback: "Clear ideas.", total_turns: 1 });
  const { state, messages } = await handleCommunicationText(chatState([
    { role: "assistant", text: "Great start!\n\nJust a small correction: Instead of “x”, you can say: “y”\n\nWhat do you like about teamwork?" },
    { role: "user", text: "I likes sharing ideas." },
    { role: "assistant", text: "Nice.\n\nTell me about a team project." },
  ]), "end_session");
  // Each AI message is sent as just the question the learner answered.
  expect(mocked.finishWritingChat).toHaveBeenCalledWith("token", "Teamwork", "medium", [
    { role: "assistant", text: "What do you like about teamwork?" },
    { role: "user", text: "I likes sharing ideas." },
    { role: "assistant", text: "Tell me about a team project." },
  ]);
  expect(state.sessionId).toBe(42);
  expect(messages[0].text).toContain("Overall score: 6.7/10");
  expect(messages[0].options?.[0]).toMatchObject({ value: "download_writing_pdf" });

  mocked.downloadWritingReportPdf.mockResolvedValue(undefined);
  await handleCommunicationText(state, "download_writing_pdf");
  expect(mocked.downloadWritingReportPdf).toHaveBeenCalledWith("token", 42);
});

test("a chat the learner never answered just ends", async () => {
  const { messages } = await handleCommunicationText(chatState([{ role: "assistant", text: "What do you think?" }]), "end_session");
  expect(mocked.finishWritingChat).not.toHaveBeenCalled();
  expect(messages[0].text).toContain("Writing chat ended");
});

test('a model reply with "null" or a copied field label is never shown to the learner', async () => {
  mocked.writingChat.mockResolvedValue({
    reply: "friendly acknowledgment Are there any experiences you find interesting?",
    reaction: "friendly acknowledgment", corrected_answer: "null",
    next_question: "Are there any experiences or themes in life that you find interesting?",
  } as never);
  const { messages } = await handleCommunicationText(chatState([{ role: "assistant", text: "What aspect of life would you like to explore?" }]), "I don't know");
  expect(messages[0].text).toBe("Are there any experiences or themes in life that you find interesting?");
  expect(messages[0].text).not.toMatch(/null|friendly acknowledgment/i);
});

test("timeout when finishing writing chat keeps retry option and allows recovery", async () => {
  mocked.finishWritingChat
    .mockRejectedValueOnce(new Error("The writing chat finish request timed out. Please try again."))
    .mockResolvedValueOnce({ session_id: 99, overall_score: 7.5, summary_feedback: "Good ideas.", total_turns: 1 });

  const initial = chatState([
    { role: "assistant", text: "What do you like about nature?" },
    { role: "user", text: "I love walking in the forest." },
  ]);
  const failed = await handleCommunicationText(initial, "end_session");
  expect(failed.state.step).toBe("writing_chat_turn");
  expect(failed.messages[0].text).toContain("timed out");
  expect(failed.messages[0].options?.map((o) => o.value)).toEqual(["end_session", "menu"]);

  const retried = await handleCommunicationText(failed.state, "end_session");
  expect(retried.state.step).toBe("main_menu");
  expect(retried.state.sessionId).toBe(99);
  expect(retried.messages[0].text).toContain("Overall score: 7.5/10");
});
