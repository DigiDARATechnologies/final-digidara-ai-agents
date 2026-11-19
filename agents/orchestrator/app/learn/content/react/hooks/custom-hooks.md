---
title: Custom hooks
summary: Extract reusable stateful logic into your own hooks, with practical examples for storage, debouncing and fetching.
takeaways:
- A custom hook is a function whose name starts with use and that calls other hooks
- Hooks share logic, not state: each call gets its own state
- Good custom hooks have a clear name and a small, simple return value
---
## Reuse logic, not markup

Components reuse **markup**. Custom hooks reuse **logic** that involves state or effects. A custom hook is just a function whose name starts with `use` and which calls other hooks.

## useToggle

```jsx
import { useState, useCallback } from "react";

function useToggle(initial = false) {
  const [on, setOn] = useState(initial);
  const toggle = useCallback(() => setOn((v) => !v), []);
  return [on, toggle];
}

function Accordion({ title, children }) {
  const [open, toggle] = useToggle(false);
  return (
    <section>
      <button onClick={toggle}>{title} {open ? "▲" : "▼"}</button>
      {open && <div>{children}</div>}
    </section>
  );
}

export default function App() {
  return (
    <div>
      <Accordion title="Closed section">Hidden</Accordion>
    </div>
  );
}
```

```output
<div>
<section>
<button>Closed section â–¼</button>
</section>
</div>
```

Each `Accordion` calls `useToggle` and gets its **own** state. Two accordions do not affect each other: hooks share the **code**, not the data.

## useLocalStorage

```jsx
function useLocalStorage(key, initialValue) {
  const [value, setValue] = useState(() => {
    try {
      const saved = localStorage.getItem(key);
      return saved !== null ? JSON.parse(saved) : initialValue;
    } catch {
      return initialValue;                         // storage blocked or invalid JSON
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {}
  }, [key, value]);

  return [value, setValue];
}

function ThemePicker() {
  const [theme, setTheme] = useLocalStorage("theme", "light");     // survives page reloads
  return <button onClick={() => setTheme(theme === "light" ? "dark" : "light")}>Theme: {theme}</button>;
}
```

`useState(() => ...)` passes a function so the storage is read only on the **first** render, not on every render (this is called lazy initialisation).

## useDebounce

Wait until the user stops typing before doing something costly like a search:

```jsx
function useDebounce(value, delay = 400) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);               // typing again cancels the pending update
  }, [value, delay]);
  return debounced;
}

function Search() {
  const [text, setText] = useState("");
  const query = useDebounce(text);               // changes 400 ms after the last keystroke
  // fetch results in an effect that depends on `query`, not on `text`
  return <input value={text} onChange={(e) => setText(e.target.value)} />;
}
```

## useFetch

```jsx
function useFetch(url) {
  const [state, setState] = useState({ status: "loading", data: null, error: null });

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: "loading", data: null, error: null });
    fetch(url, { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("HTTP " + r.status))))
      .then((data) => setState({ status: "done", data, error: null }))
      .catch((error) => error.name !== "AbortError" && setState({ status: "error", data: null, error }));
    return () => controller.abort();
  }, [url]);

  return state;
}

function Courses() {
  const { status, data, error } = useFetch("/api/courses");
  if (status === "loading") return <p>Loading...</p>;
  if (status === "error") return <p>{error.message}</p>;
  return <ul>{data.map((c) => <li key={c.id}>{c.title}</li>)}</ul>;
}
```

The component stays small and readable because the messy fetch logic is hidden behind one name. For production apps, a library such as **TanStack Query** adds caching, retries and background refresh on top of this idea.

## Good habits

| Habit | Why |
| --- | --- |
| Name it `useSomething` | the linter then checks the rules of hooks inside it |
| Return only what callers need | a small, stable API |
| Do one thing | `useDebounce` and `useFetch` are better than `useEverything` |
| Do not use a hook just to hide one `useState` | extra indirection without a benefit |

:::interview
**Interviewers often ask:** "Do two components that use the same custom hook share state?" No. Each call to a hook creates its own independent state. To share state, lift it up or use context.
:::
