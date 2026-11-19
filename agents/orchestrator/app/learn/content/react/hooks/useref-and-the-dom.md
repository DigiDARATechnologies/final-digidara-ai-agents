---
title: useRef and the DOM
summary: Reach a DOM element, keep values that do not trigger renders, and learn when refs are the right tool.
takeaways:
- A ref holds a value that survives renders but does not cause a re-render when changed
- Refs are how you focus, scroll to or measure a DOM element
- Do not read or write ref.current during rendering
---
## A box that React does not watch

`useRef(initial)` returns an object `{ current: initial }` that stays **the same object** across renders. Changing `ref.current` does **not** re-render the component, which makes it different from state.

| | State | Ref |
| --- | --- | --- |
| Survives re-renders | yes | yes |
| Changing it re-renders | **yes** | **no** |
| Use for | anything shown on screen | things that do not affect the screen |

## Use 1: reach a DOM element

```jsx
import { useRef, useEffect } from "react";

function SearchBox() {
  const inputRef = useRef(null);

  useEffect(() => {
    inputRef.current.focus();            // after mount, the ref points at the real <input>
  }, []);

  return <input ref={inputRef} placeholder="Search..." />;
}
```

Attach the ref with the `ref` prop, and React sets `inputRef.current` to the DOM node once it exists. Typical uses: focus an input, scroll an element into view, play a video, measure a size.

```jsx
function MessageList({ messages }) {
  const endRef = useRef(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });   // scroll to the newest message
  }, [messages]);

  return (
    <ul>
      {messages.map((m) => <li key={m.id}>{m.text}</li>)}
      <li ref={endRef} />
    </ul>
  );
}
```

## Use 2: remember a value without re-rendering

A timer id, the previous value of a prop, or "has this already run?" are not shown on screen, so they fit a ref:

```jsx
function Stopwatch() {
  const [seconds, setSeconds] = useState(0);
  const timerRef = useRef(null);              // the interval id: not shown, so not state

  function start() {
    if (timerRef.current) return;
    timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
  }
  function stop() {
    clearInterval(timerRef.current);
    timerRef.current = null;
  }

  return (
    <div>
      <p>{seconds}s</p>
      <button onClick={start}>Start</button>
      <button onClick={stop}>Stop</button>
    </div>
  );
}
```

Here is a ref used on the first render, to show that its value is there and `current` starts as given:

```jsx
import { useRef } from "react";

export default function App() {
  const renders = useRef(0);
  renders.current += 1;                     // for demonstration only: normally do this in an effect or handler
  const inputRef = useRef(null);

  return (
    <div>
      <p>Render number {renders.current}</p>
      <p>Input ref starts as: {String(inputRef.current)}</p>
      <input ref={inputRef} />
    </div>
  );
}
```

```output
<div>
<p>Render number 1</p>
<p>Input ref starts as: null</p>
<input/></div>
```

The input ref is `null` during rendering because the DOM element does not exist yet; it is filled in after React commits.

:::warning
Do not read or write `ref.current` **during rendering** (except for one-time set-up). Rendering must be pure. Use refs inside **event handlers and effects**.
:::

## Passing a ref to your own component

In React 19, `ref` is an ordinary prop for function components, so a child can accept it directly:

```jsx
function TextInput({ ref, ...props }) {      // React 19: ref arrives as a prop
  return <input ref={ref} {...props} />;
}

function Form() {
  const inputRef = useRef(null);
  return (
    <>
      <TextInput ref={inputRef} />
      <button onClick={() => inputRef.current.focus()}>Focus</button>
    </>
  );
}
```

In React 18 and earlier, wrap the child in `forwardRef` to receive the ref as a second argument.

:::tip
If you find yourself using a ref to copy data into the page by hand (setting `innerHTML`, changing text), stop. Put that data in state and let React render it. Refs are for the cases React cannot express: focus, scroll, measurements and third-party widgets.
:::
