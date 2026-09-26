import { fireEvent, render, screen } from "@testing-library/react";
import SearchChatsModal from "../../src/components/SearchChatsModal";
import type { Chat } from "../../src/types";

const msg = (text: string) => ({ role: "user" as const, text, time: "10:00" });
const chats: Chat[] = [
  { id: "a", agentId: "aptitude", title: "Percentages practice", messages: [msg("hello")], updatedAt: Date.now() - 60_000 },
  { id: "b", agentId: "resume-builder", title: "My resume", messages: [msg("please improve my summary section")], updatedAt: Date.now() - 3_600_000 },
];

test("with no query it lists recent chats", () => {
  render(<SearchChatsModal chats={chats} onOpenChat={() => {}} onClose={() => {}} />);
  expect(screen.getByText("Recent chats")).toBeInTheDocument();
  expect(screen.getByText("Percentages practice")).toBeInTheDocument();
  expect(screen.getByText("My resume")).toBeInTheDocument();
});

test("matches on the title and on message text", () => {
  render(<SearchChatsModal chats={chats} onOpenChat={() => {}} onClose={() => {}} />);
  const input = screen.getByPlaceholderText("Search chats…");
  fireEvent.change(input, { target: { value: "percent" } });
  expect(screen.getByText("1 result")).toBeInTheDocument();
  // The match is wrapped in <mark>, so compare the list's combined text.
  const list = () => document.querySelector(".sc-list")?.textContent ?? "";
  expect(list()).toContain("Percentages practice");
  expect(list()).not.toContain("My resume");
  fireEvent.change(input, { target: { value: "summary" } });
  expect(list()).toContain("My resume");
  expect(list()).not.toContain("Percentages practice");
});

test("shows an empty state, and Enter opens the highlighted chat then closes", () => {
  const onOpenChat = jest.fn();
  const onClose = jest.fn();
  render(<SearchChatsModal chats={chats} onOpenChat={onOpenChat} onClose={onClose} />);
  const input = screen.getByPlaceholderText("Search chats…");
  fireEvent.change(input, { target: { value: "zzzz" } });
  expect(screen.getByText(/No chats found/)).toBeInTheDocument();
  fireEvent.change(input, { target: { value: "resume" } });
  fireEvent.keyDown(input, { key: "Enter" });
  expect(onOpenChat).toHaveBeenCalledWith("b");
  expect(onClose).toHaveBeenCalled();
});
