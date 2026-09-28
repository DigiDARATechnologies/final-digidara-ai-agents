import { getDisplayRating, markAsked, shouldAskForRating, submitRating } from "../../src/lib/ratings";

beforeEach(() => localStorage.clear());

test("a new 5-star rating raises an agent's rating and count", () => {
  expect(getDisplayRating("aptitude", 4.5)).toEqual({ value: 4.5, count: 0 });
  submitRating("u1", "aptitude", 5);
  const after = getDisplayRating("aptitude", 4.5);
  expect(after.count).toBe(1);
  expect(after.value).toBeCloseTo((4.5 * 5 + 5) / 6, 5);
  expect(after.value).toBeGreaterThan(4.5);
});

test("rating the same agent again replaces the earlier vote instead of stacking", () => {
  submitRating("u1", "aptitude", 5);
  submitRating("u1", "aptitude", 1);
  const after = getDisplayRating("aptitude", 4.5);
  expect(after.count).toBe(1);
  expect(after.value).toBeCloseTo((4.5 * 5 + 1) / 6, 5);
});

test("different users each add a vote", () => {
  submitRating("u1", "job-fetch", 4);
  submitRating("u2", "job-fetch", 5);
  expect(getDisplayRating("job-fetch", 4.6).count).toBe(2);
});

test("the prompt is asked once per chat and at most once a day per agent", () => {
  expect(shouldAskForRating("u1", "aptitude", "chat-1")).toBe(true);
  markAsked("u1", "aptitude", "chat-1");
  expect(shouldAskForRating("u1", "aptitude", "chat-1")).toBe(false);
  expect(shouldAskForRating("u1", "aptitude", "chat-2")).toBe(false);
  expect(shouldAskForRating("u1", "job-fetch", "chat-3")).toBe(true);
});
