---
title: React interview questions
summary: React questions from basic to advanced, with answers you can say aloud in an interview.
kind: qa
takeaways:
- Be able to explain state, props, the render cycle and the rules of hooks clearly
- Know why keys matter, how effects and cleanup work, and when not to use an effect
- Have a performance, state-management and testing answer ready
---
### Q [Easy] What is React and why use it?
A JavaScript library for building user interfaces from reusable components. You describe what the UI should look like for the current data, and React updates the DOM efficiently when the data changes. Benefits: reusable components, a predictable one-way data flow and a big ecosystem.

### Q [Easy] What is JSX?
A syntax extension that lets you write markup inside JavaScript. A build tool compiles it into function calls that create React elements. It is not HTML: for example it uses `className` and `htmlFor`, and expressions go in curly braces.

### Q [Easy] What is the difference between props and state?
Props are inputs passed from a parent and are read-only. State is data a component owns and remembers between renders; changing it with its setter triggers a re-render.

### Q [Easy] What is a component, and what is the difference between a function and a class component?
A component is a reusable piece of UI that returns markup. Function components with hooks are the modern standard. Class components use `this.state` and lifecycle methods and are still supported, but new code uses functions (error boundaries are the main remaining use of classes).

### Q [Medium] Why do we need keys in lists?
Keys give each item a stable identity so React can match old and new items when a list changes, and preserve each item's state and DOM correctly. Use a unique stable id; avoid the array index if the list can reorder, insert or delete, and never use a random value.

### Q [Medium] What are the rules of hooks?
Call hooks only at the top level of a component or custom hook (not inside loops, conditions or nested functions), and only from React function components or custom hooks. React relies on the call order being the same on every render.

### Q [Medium] How does useEffect work, and what is the dependency array?
It runs after render to synchronise with something outside React (data, timers, subscriptions). With `[]` it runs once after mount; with dependencies it runs after the first render and whenever one changes; with none it runs after every render. A returned function is the cleanup and runs before the next effect and on unmount.

### Q [Medium] Why would you return a cleanup function from an effect?
To undo what the effect started: clear timers, remove event listeners, unsubscribe, abort fetches. It prevents memory leaks and stale updates, and it keeps effects correct when React Strict Mode runs them twice in development.

### Q [Medium] What is the difference between controlled and uncontrolled components?
A controlled input's value comes from React state and changes through `onChange`, so React is the source of truth. An uncontrolled input keeps its own value in the DOM and you read it with a ref or `FormData`. Controlled suits live validation; uncontrolled suits simple forms.

### Q [Medium] What is lifting state up?
Moving shared state to the closest common parent of the components that need it, and passing it down as props together with functions to update it, so there is a single source of truth.

### Q [Medium] What is prop drilling, and how can you avoid it?
Passing props through many layers that do not use them. Avoid it with context for broadly shared values, with composition (passing elements or `children`), or with a state library for complex shared state.

### Q [Medium] When does a component re-render?
When its own state changes, when its parent re-renders, or when a context it consumes changes. Re-rendering runs the function again; React then updates only the DOM parts that actually differ.

### Q [Hard] What do memo, useMemo and useCallback do, and when should you use them?
`memo` skips re-rendering a component when its props are shallowly equal. `useMemo` caches a calculated value and `useCallback` caches a function between renders until dependencies change. Use them for genuinely expensive work or to keep stable references for memoized children or effect dependencies, after measuring with the Profiler; not by default.

### Q [Hard] Why is mutating state a problem?
React decides whether to re-render by checking if the new state is a different value (by reference). Mutating an object or array in place and passing the same reference gives no change signal, so the UI may not update, and it breaks features that rely on previous snapshots. Always create new objects or arrays with spread, `map` or `filter`.

### Q [Hard] What is the virtual DOM and reconciliation?
React builds a lightweight description of the UI for each render. On updates it compares the new description with the previous one (reconciliation) using type and key to match elements, and applies only the minimal real DOM changes. It makes declarative UIs efficient enough without manual DOM updates.

### Q [Medium] When should you use useReducer instead of useState?
When state has several related values or many kinds of updates, or the next state depends on rules worth testing in isolation. A reducer centralises update logic as a pure function `(state, action) => newState`, and `dispatch` keeps components simple.

### Q [Medium] What are error boundaries?
Components that catch errors thrown while rendering their children and show a fallback instead of crashing the whole tree. They are class components using `getDerivedStateFromError` and `componentDidCatch`. They do not catch errors in event handlers or async code.

### Q [Hard] How would you improve the performance of a slow React app?
Measure with the Profiler first. Then move state down, avoid unnecessary re-renders with `memo` where it matters, virtualise long lists, code-split routes with `lazy`, memoise expensive calculations, use transitions for heavy updates, and optimise network usage with caching (TanStack Query).

### Q [Hard] How do you handle server data versus UI state?
Treat API data as a cache and manage it with TanStack Query or SWR (loading and error states, caching, refetching, invalidation after mutations). Keep UI state local with `useState` or `useReducer`, share app-wide values with context, and keep filters and pages in the URL.

### Q [Hard] What is the difference between client-side and server-side rendering, and what are server components?
Client-side rendering builds the page in the browser from JavaScript. Server-side rendering sends ready HTML for a faster first view and better SEO, then hydrates it. Server components run only on the server and send no JavaScript for those parts, so they can access data directly and keep bundles small; interactive parts remain client components.

### Q [Hard] How do you secure and make a React app accessible?
Never trust the client: authorise on the server, avoid `dangerouslySetInnerHTML` with untrusted input (React escapes values by default), keep tokens out of places scripts can read where possible, and update dependencies. For accessibility use semantic HTML, labels, keyboard support, managed focus and live regions, and test with linting, axe and a screen reader.

:::practice mock-interview
Practise explaining state, effects with cleanup and re-rendering aloud in a Mock Interview.
:::
