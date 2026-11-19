---
title: What is React?
summary: React builds user interfaces from small reusable components. See the big idea, set up a project and read your first component.
takeaways:
- React describes what the screen should look like for the current data, and updates it for you
- A UI is a tree of components, each one a function that returns markup
- Vite is the quickest way to start a React project today
---
## The problem React solves

On a page with a cart count, a list of products and a "total" box, one click must update many places. With plain JavaScript you find each element and change it by hand, and as the page grows it is easy to forget one, so the screen and the data disagree.

React flips this around. You write **what the screen should look like for the current data**, and React works out the smallest set of changes to make it so.

| Plain JavaScript | React |
| --- | --- |
| "find the badge, change its text, find the list, add an item..." | "the badge shows `items.length`; the list shows `items`" |
| you update the page step by step | you update the **data**; the page follows |
| easy to get out of sync | the screen is always a function of the data |

## Components

A React app is a **tree of components**. A component is a JavaScript function that returns markup (JSX).

```jsx
function Greeting() {
  return <h1>Hello from a component</h1>;
}

export default function App() {
  return (
    <main>
      <Greeting />
      <Greeting />
    </main>
  );
}
```

```output
<main><h1>Hello from a component</h1>
<h1>Hello from a component</h1>
</main>
```

`<Greeting />` is used like an HTML tag, and each use produces its own copy. The output above is the real HTML that React produced.

## Start a project

Use **Vite**, a fast development tool:

```py
npm create vite@latest my-app -- --template react
cd my-app
npm install
npm run dev
```

Open the address it prints (usually http://localhost:5173). Edit `src/App.jsx`, and the browser updates as you save.

```py
my-app/
  index.html          # the one HTML page, with <div id="root">
  src/
    main.jsx          # starts React and mounts <App /> into #root
    App.jsx           # your first component
    index.css
  package.json        # scripts and dependencies
```

```jsx
import { createRoot } from "react-dom/client";
import App from "./App";

createRoot(document.getElementById("root")).render(<App />);
```

That is the whole start-up: find the `#root` element and tell React to draw `<App />` inside it.

## Libraries and frameworks

| Tool | What it adds |
| --- | --- |
| **React** | the component model, state and hooks |
| **Vite** | dev server and build for a single-page app |
| **React Router** | pages and URLs |
| **Next.js, Remix** | frameworks with routing, server rendering and more |
| **TanStack Query** | data fetching and caching |

This course teaches React itself, which every one of those tools builds on.

:::tip
You need to be comfortable with JavaScript first: functions, arrays (`map`, `filter`), objects, destructuring and arrow functions. If any of these feel shaky, revisit the JavaScript course before starting.
:::
