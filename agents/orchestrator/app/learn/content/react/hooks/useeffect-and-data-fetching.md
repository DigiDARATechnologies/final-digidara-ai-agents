---
title: useEffect and data fetching
summary: Run side effects after render, fetch data safely with cleanup, and know when you do not need an effect.
takeaways:
- An effect runs after rendering and syncs your component with something outside React
- The dependency array controls when the effect re-runs; return a function to clean up
- Many things people put in effects belong in render or event handlers instead
---
## What is an effect?

Rendering must be a pure calculation: same props and state in, same markup out. But apps also need to **do** things: fetch data, start a timer, listen for a window event, change the page title. These are **side effects**, and they go in `useEffect`, which runs **after** React has put the UI on screen.

```jsx
import { useEffect, useState } from "react";

function Clock() {
  const [time, setTime] = useState(() => new Date().toLocaleTimeString());

  useEffect(() => {
    const id = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(id);        // cleanup: runs before the next effect and on unmount
  }, []);                                  // [] = run once, after the first render

  return <p>{time}</p>;
}
```

## The dependency array

| You write | Effect runs |
| --- | --- |
| `useEffect(fn)` | after **every** render (rarely wanted) |
| `useEffect(fn, [])` | once, after the first render |
| `useEffect(fn, [userId])` | after the first render and whenever `userId` changes |

List **every value from the component** (props, state, functions) that the effect uses. The ESLint rule `react-hooks/exhaustive-deps` checks it for you; follow it.

## Fetching data correctly

A naive fetch has a bug: if `userId` changes quickly, an old, slower response can arrive **after** a new one and overwrite it. Clean up to ignore stale responses:

```jsx
function Profile({ userId }) {
  const [state, setState] = useState({ status: "loading", user: null, error: null });

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: "loading", user: null, error: null });

    fetch(`/api/users/${userId}`, { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then((user) => setState({ status: "done", user, error: null }))
      .catch((error) => {
        if (error.name !== "AbortError") setState({ status: "error", user: null, error });
      });

    return () => controller.abort();       // cancel the request if userId changes or we unmount
  }, [userId]);

  if (state.status === "loading") return <p>Loading...</p>;
  if (state.status === "error") return <p role="alert">Failed: {state.error.message}</p>;
  return <h2>{state.user.name}</h2>;
}
```

Three habits here matter: check `res.ok` (fetch does not throw for a 404), handle the error state, and **abort** in the cleanup.

The component below uses the same three states. Since effects do not run on the server, this render shows the starting "loading" state:

```jsx
import { useEffect, useState } from "react";

export default function App() {
  const [status, setStatus] = useState("loading");
  const [name, setName] = useState(null);

  useEffect(() => {
    setStatus("done");
    setName("Asha");
  }, []);

  return status === "loading" ? <p>Loading...</p> : <h2>{name}</h2>;
}
```

```output
<p>Loading...</p>
```

## You might not need an effect

Effects are for syncing with the **outside world**. Many uses are mistakes:

| Instead of an effect that... | Do this |
| --- | --- |
| computes `fullName` from `first` and `last` and stores it in state | just calculate it during render: `const fullName = first + " " + last` |
| filters a list into another state variable | derive it in render (use `useMemo` only if it is slow) |
| reacts to a button click | put the code in the **event handler** |
| resets state when a prop changes | give the component a `key={id}` so it remounts |
| fetches data in a large app | use a data library (TanStack Query, SWR) or a framework loader |

:::warning
Setting state inside an effect that depends on that same state creates an **infinite loop** (set, render, effect, set...). If an effect runs forever, check what it updates and what it lists in the dependency array.
:::

## Strict Mode

In development, React's `<StrictMode>` runs every effect **twice** (mount, unmount, mount) to reveal missing cleanups. If your effect breaks when run twice, it has a bug that cleanup should fix (an interval that is never cleared, a listener never removed). This does not happen in production.

:::interview
**Interviewers often ask:** "Why is cleanup in useEffect needed?" To undo what the effect started (timers, subscriptions, event listeners, in-flight requests) when the component unmounts or before the effect runs again, so you avoid memory leaks and stale updates.
:::
