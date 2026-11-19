---
title: State with useState
summary: Make components remember and change values with useState, and learn how React re-renders.
takeaways:
- State is data a component remembers between renders
- Calling the setter schedules a re-render with the new value
- Never change state directly; always produce a new value
---
## Why a normal variable is not enough

If you change an ordinary variable, React does not know, so the screen does not update, and the variable resets on the next render anyway. Data that changes over time must live in **state**.

## useState

```jsx
import { useState } from "react";

export default function App() {
  const [count, setCount] = useState(0);

  return (
    <div>
      <p>Clicked {count} times</p>
      <button onClick={() => setCount(count + 1)}>Add one</button>
    </div>
  );
}
```

```output
<div>
<p>Clicked 0 times</p>
<button>Add one</button>
</div>
```

`useState(0)` returns a pair: the current value (`count`, starting at `0`) and a function to change it (`setCount`). When you call `setCount`, React **re-renders** the component with the new value. (This page shows the first render; the click handler runs in a browser.)

| Part | Meaning |
| --- | --- |
| `count` | the current value |
| `setCount(next)` | replace the value and re-render |
| `useState(0)` | `0` is the starting value, used only on the first render |

## Rules of hooks

Functions starting with `use` are **hooks**. They have two rules:

1. Call them only at the **top level** of a component (not in loops, conditions or nested functions).
2. Call them only from components or from other hooks.

React tracks hooks by the **order** they are called, so the order must be the same every render.

## State is a snapshot

When a component renders, `count` is a fixed value for that render. Calling `setCount(count + 1)` three times in one handler adds **one**, because every call sees the same old `count`. Use the **updater form** when the new value depends on the old one:

```jsx
function handleClick() {
  setCount(count + 1);
  setCount(count + 1);
  setCount(count + 1);     // all three set the same number: count + 1
}

function handleClickCorrectly() {
  setCount((c) => c + 1);
  setCount((c) => c + 1);
  setCount((c) => c + 1);  // each receives the latest value: adds three
}
```

## Never mutate state

For objects and arrays, create a **new** copy. React decides whether to re-render by checking if the value is a new one.

```jsx
import { useState } from "react";

export default function App() {
  const [todos, setTodos] = useState([{ id: 1, text: "Learn JSX", done: true }]);

  // these show the correct update patterns; they run when called from event handlers
  const add = (text) => setTodos([...todos, { id: Date.now(), text, done: false }]);
  const toggle = (id) => setTodos(todos.map((t) => (t.id === id ? { ...t, done: !t.done } : t)));
  const remove = (id) => setTodos(todos.filter((t) => t.id !== id));

  return (
    <ul>
      {todos.map((t) => (
        <li key={t.id}>
          <input type="checkbox" checked={t.done} readOnly /> {t.text}
        </li>
      ))}
    </ul>
  );
}
```

```output
<ul>
<li><input type="checkbox" readOnly="" checked=""/> Learn JSX</li>
</ul>
```

| Task | Immutable pattern |
| --- | --- |
| add to an array | `[...items, newItem]` |
| remove from an array | `items.filter(i => i.id !== id)` |
| change one item | `items.map(i => i.id === id ? { ...i, done: true } : i)` |
| change an object field | `{ ...user, name: "Asha" }` |

:::warning
`todos.push(x)` followed by `setTodos(todos)` does **not** work: it is the same array, so React sees no change and may skip the update. Always pass a new array or object.
:::

## Where should state live?

Keep state in the **nearest common parent** of every component that needs it. This is called **lifting state up**. If two siblings need the same value, move it to their parent and pass it down as props.

:::interview
**Interviewers often ask:** "What is the difference between props and state?" Props are passed in by the parent and are read-only. State is owned by the component, can change, and changing it triggers a re-render.
:::
