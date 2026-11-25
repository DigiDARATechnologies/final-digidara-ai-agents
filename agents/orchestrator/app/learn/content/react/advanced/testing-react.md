---
title: Testing React components
summary: Test like a user with Vitest and React Testing Library: render, query by role, simulate events and mock the network.
takeaways:
- Test what the user sees and does, not the component's internal state
- Query by role and label, the way assistive technology finds elements
- Mock the network, not your own components
---
## What to test

A good React test answers: "when the user does X, do they see Y?" It does not check that a state variable has a certain value, because that is an implementation detail that breaks when you refactor.

| Tool | Role |
| --- | --- |
| **Vitest** (or Jest) | the test runner |
| **React Testing Library** | render components and query them like a user |
| **user-event** | realistic typing and clicking |
| **MSW** (Mock Service Worker) | fake the API at the network level |

```py
npm install -D vitest jsdom @testing-library/react @testing-library/user-event @testing-library/jest-dom
```

## A first test

The component:

```jsx
import { useState } from "react";

export function Counter() {
  const [count, setCount] = useState(0);
  return (
    <div>
      <p>Count: {count}</p>
      <button onClick={() => setCount(count + 1)}>Add one</button>
    </div>
  );
}
```

The test:

```jsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Counter } from "./Counter";

test("adds one when the button is clicked", async () => {
  const user = userEvent.setup();
  render(<Counter />);

  expect(screen.getByText("Count: 0")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /add one/i }));

  expect(screen.getByText("Count: 1")).toBeInTheDocument();
});
```

The test never touches `count`. It clicks the button like a person and reads the screen.

## Queries: pick the most accessible one

In priority order:

| Query | When |
| --- | --- |
| `getByRole("button", { name: /save/i })` | almost always the first choice |
| `getByLabelText("Email")` | form fields |
| `getByText("Welcome")` | non-interactive text |
| `getByPlaceholderText` | only if there is no label |
| `getByTestId("x")` | last resort, when nothing else works |

The three families:

| Prefix | Meaning |
| --- | --- |
| `getBy...` | must exist now, else the test fails |
| `queryBy...` | returns `null` if missing: use to assert something is **not** there |
| `findBy...` | waits for it to appear (for async updates) |

## Testing a form

```jsx
test("shows an error for a bad email, then accepts a good one", async () => {
  const user = userEvent.setup();
  const onSubmit = vi.fn();
  render(<SignupForm onSubmit={onSubmit} />);

  await user.type(screen.getByLabelText(/email/i), "not-an-email");
  await user.click(screen.getByRole("button", { name: /sign up/i }));
  expect(screen.getByRole("alert")).toHaveTextContent(/valid email/i);
  expect(onSubmit).not.toHaveBeenCalled();

  await user.clear(screen.getByLabelText(/email/i));
  await user.type(screen.getByLabelText(/email/i), "asha@example.com");
  await user.click(screen.getByRole("button", { name: /sign up/i }));
  expect(onSubmit).toHaveBeenCalledWith({ email: "asha@example.com" });
});
```

## Testing async data

```jsx
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

const server = setupServer(
  http.get("/api/courses", () => HttpResponse.json([{ id: 1, title: "Python" }]))
);
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

test("shows courses after loading", async () => {
  render(<Courses />);
  expect(screen.getByText(/loading/i)).toBeInTheDocument();
  expect(await screen.findByText("Python")).toBeInTheDocument();      // waits for the response
});

test("shows an error when the API fails", async () => {
  server.use(http.get("/api/courses", () => new HttpResponse(null, { status: 500 })));
  render(<Courses />);
  expect(await screen.findByRole("alert")).toHaveTextContent(/could not load/i);
});
```

Test the **error and empty** paths as well as the happy one. Those are the ones that break in production.

## Testing custom hooks

```jsx
import { renderHook, act } from "@testing-library/react";

test("useToggle flips the value", () => {
  const { result } = renderHook(() => useToggle(false));
  expect(result.current[0]).toBe(false);
  act(() => result.current[1]());
  expect(result.current[0]).toBe(true);
});
```

## Test pure logic directly

Reducers, validators and formatters are plain functions: test them without rendering anything. They are the fastest, most reliable tests you will write.

```jsx
test("the cart reducer merges duplicate items", () => {
  let state = { items: [], coupon: null };
  const pen = { id: 1, name: "Pen", price: 10 };
  state = cartReducer(state, { type: "add", item: pen });
  state = cartReducer(state, { type: "add", item: pen });
  expect(state.items).toEqual([{ ...pen, qty: 2 }]);
});
```

## Habits

| Do | Avoid |
| --- | --- |
| query by role and label | querying by CSS class or component names |
| use `userEvent` | `fireEvent` for ordinary interactions |
| `await` async queries (`findBy`) | `setTimeout` or fixed waits in tests |
| mock the network edge | mocking your own child components |
| one behaviour per test | long tests that check ten things |

For whole flows across pages (log in, buy a course, see the receipt) use an end-to-end tool such as **Playwright**.

:::interview
**Interviewers often ask:** "How do you test React components?" With React Testing Library: render the component, interact as a user would (find by role or label, click, type), and assert on visible output. Mock the network rather than internals, and test reducers and utilities as plain functions.
:::
