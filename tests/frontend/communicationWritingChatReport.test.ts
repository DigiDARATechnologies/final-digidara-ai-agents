jest.mock("../../src/lib/communicationApi", () => ({
  finishWritingChat: jest.fn(),
  downloadWritingReportPdf: jest.fn(),
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
