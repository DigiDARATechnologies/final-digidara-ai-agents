---
title: Rendering and performance
summary: Understand when React re-renders, then use memo, useMemo, useCallback and the profiler to fix real slowness, not imagined slowness.
takeaways:
- A component re-renders when its state changes, its parent re-renders, or its context changes
- Measure with the React DevTools Profiler first; most apps need very little optimisation
- memo, useMemo and useCallback only help when the work is expensive and the inputs are stable
---
## When does React re-render?

A component re-renders when:

1. its **own state** changes,
2. its **parent re-renders** (even if its props did not change),
3. a **context** it reads changes.

Re-rendering is just running the function again: cheap for most components. React then compares the result with the previous one and updates only the real differences in the page. So re-rendering is **not** the same as repainting the screen.

## See it happen

Add a log line to a component and you can watch it:

```jsx
function Child({ name }) {
  console.log("render", name);          // appears in the browser console on every render
  return <li>{name}</li>;
}

function Parent() {
  const [count, setCount] = useState(0);
  return (
    <>
      <button onClick={() => setCount(count + 1)}>{count}</button>
      <ul>
        <Child name="a" />
        <Child name="b" />
      </ul>
    </>
  );
}
```

Each click changes `Parent`'s state, so `Parent` re-renders, and both `Child` components re-render with it, even though their props never changed. The console shows `render a` and `render b` after every click.

## memo

`memo(Component)` tells React: "skip re-rendering this component if its props are the **same** as last time" (compared with `Object.is`, shallowly).

```jsx
import { memo } from "react";

const Row = memo(function Row({ label }) {
  console.log("render", label);
  return <li>{label}</li>;
});
```

With this change, clicking the parent's button no longer logs `render a` or `render b` again: the props (`label`) are the same, so React skips those components. The first render always happens; `memo` only prevents **later** re-renders when props are unchanged.

But memo is easy to defeat. Objects, arrays and functions created inside a component are **new every render**, so they are "different" each time:

```jsx
const Row = memo(RowComponent);

function List() {
  const [count, setCount] = useState(0);

  return (
    <>
      <button onClick={() => setCount(count + 1)}>{count}</button>
      {/* BAD: a new object and a new function each render, so memo never skips */}
      <Row style={{ color: "teal" }} onSelect={() => console.log("pick")} />
    </>
  );
}
```

## useMemo and useCallback

- **`useMemo(fn, deps)`** remembers a **value** and recalculates only when `deps` change.
- **`useCallback(fn, deps)`** remembers a **function**, so its identity stays the same.

```jsx
function List({ items, query }) {
  const [count, setCount] = useState(0);

  // expensive work: recomputed only when items or query change, not when count changes
  const visible = useMemo(
    () => items.filter((i) => i.name.toLowerCase().includes(query.toLowerCase())),
    [items, query]
  );

  // a stable function, so a memoized child does not see a "new" prop each time
  const handleSelect = useCallback((id) => console.log("selected", id), []);

  return (
    <>
      <button onClick={() => setCount(count + 1)}>{count}</button>
      {visible.map((i) => <Row key={i.id} item={i} onSelect={handleSelect} />)}
    </>
  );
}
```

The calculation inside `useMemo` runs on the first render. On later renders caused by `count` changing, React sees that `items` and `query` are unchanged and **reuses the stored list**. If `items` were a new array, it would filter again.

:::warning
Do not wrap everything in `memo`, `useMemo` and `useCallback`. They have a cost (memory and comparisons) and make code harder to read. Add them when the **Profiler** shows a real problem. In React 19 the **React Compiler** can apply this memoisation automatically.
:::

## Cheaper fixes first

| Problem | Better fix than memo |
| --- | --- |
| a typing box slows the whole page | **move state down** into a small component so the rest does not re-render |
| a huge list is slow | **virtualise** it: render only visible rows (react-window, TanStack Virtual) |
| expensive component under rarely-changing state | pass it as `children` so it is created by the parent that does not re-render |
| a big calculation | memoise it, or move it to the server or a web worker |
| a slow first load | **code-split** with `lazy` (next lesson) |

Moving state down is often the fastest win:

```jsx
// Slow: typing re-renders <ExpensiveTree /> on every keystroke
function Page() {
  const [text, setText] = useState("");
  return (
    <>
      <input value={text} onChange={(e) => setText(e.target.value)} />
      <ExpensiveTree />
    </>
  );
}

// Fast: the state lives in a small component, so <ExpensiveTree /> is untouched
function SearchBox() {
  const [text, setText] = useState("");
  return <input value={text} onChange={(e) => setText(e.target.value)} />;
}
function PageFast() {
  return (
    <>
      <SearchBox />
      <ExpensiveTree />
    </>
  );
}
```

## Keys and identity

React keeps a component's state only while it stays in the **same position with the same type** (and key). Changing the `key` **resets** the state, which is a handy way to reset a form:

```jsx
<ProfileForm key={user.id} user={user} />;      // a different user: a fresh form, no leftover input
```

## How to measure

1. Install **React Developer Tools** in your browser.
2. Open the **Profiler** tab, press record, perform the slow action, stop.
3. Look at the flame chart for components that rendered often or for a long time.
4. Make one change, measure again.

:::interview
**Interviewers often ask:** "When would you use useMemo or useCallback?" When a calculation is genuinely expensive, or when a stable reference is needed, for instance to avoid re-rendering a `memo` child or as an effect dependency. Not by default, because unnecessary memoisation adds cost and complexity.
:::
