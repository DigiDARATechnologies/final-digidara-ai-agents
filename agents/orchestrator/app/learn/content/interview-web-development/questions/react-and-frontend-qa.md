---
title: React and frontend questions
summary: Components, props and state, hooks, rendering, keys, performance and state management.
kind: qa
takeaways:
- Explain props versus state and the main hooks
- Know how React updates the DOM and why keys matter
- Discuss performance and state management choices
---
### Q [Easy] What is React?
A JavaScript library for building user interfaces from reusable **components**, which describe what the UI should look like for the current data.

### Q [Easy] What is JSX?
A syntax that looks like HTML inside JavaScript. It is compiled to function calls that create React elements.

### Q [Easy] Props vs state?
**Props** are inputs passed from a parent to a child and are read-only. **State** is data owned by a component that can change over time and triggers a re-render when updated.

### Q [Medium] What is the virtual DOM?
A lightweight copy of the UI in memory. When state changes React builds a new virtual tree, compares it with the previous one (**diffing**), and updates only the real DOM parts that changed.

### Q [Medium] Why are `key` props important in lists?
Keys let React identify which items changed, were added or removed, so it updates efficiently and keeps component state correct. Use a stable unique id, not the array index when the list can change order.

### Q [Medium] Explain `useState` and `useEffect`.
`useState` adds state: `const [count, setCount] = useState(0)`. `useEffect` runs side effects (fetching data, subscriptions) after rendering; the dependency array controls when it runs, and the returned function cleans up.

```jsx
useEffect(() => {
  const id = setInterval(tick, 1000);
  return () => clearInterval(id);   // cleanup
}, []);                              // run once
```

### Q [Medium] What happens if you leave the dependency array out?
The effect runs after **every** render, which can cause repeated work or infinite loops if the effect updates state.

### Q [Medium] Controlled vs uncontrolled components?
A **controlled** input's value is held in React state and updated through `onChange`. An **uncontrolled** input keeps its own value in the DOM, read through a `ref`. Controlled inputs are the usual choice for forms with validation.

### Q [Medium] Why must state not be changed directly?
React detects changes through new references. Mutating the old object or array does not trigger a re-render and can cause bugs; create a new copy (`setList([...list, item])`).

### Q [Medium] `useMemo`, `useCallback` and `React.memo`?
They avoid unnecessary work. `useMemo` caches a computed value, `useCallback` caches a function, and `React.memo` skips re-rendering a component when its props did not change. Use them when you measure a real performance problem.

### Q [Medium] What is prop drilling and how can you avoid it?
Passing props through many layers that do not use them. Avoid with the **Context API**, composition, or a state library (Redux, Zustand).

### Q [Hard] When would you use Context vs Redux?
Context suits low-frequency shared values (theme, user). A state library suits large, frequently changing or complex shared state with tools for debugging and structure.

### Q [Medium] What is lifting state up?
Moving shared state to the nearest common parent so sibling components can use the same data.

### Q [Hard] How do you optimise a slow React app?
Measure first with the Profiler. Then reduce re-renders (`React.memo`, stable props), split code (`lazy` and `Suspense`), virtualise long lists, avoid heavy work in render, and debounce expensive inputs.
