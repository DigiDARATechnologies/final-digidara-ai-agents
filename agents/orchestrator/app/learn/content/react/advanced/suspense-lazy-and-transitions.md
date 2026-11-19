---
title: Suspense, lazy loading and transitions
summary: Split your bundle with lazy, show fallbacks with Suspense, keep typing smooth with transitions, and meet the newest React features.
takeaways:
- lazy and Suspense load code only when it is needed
- useTransition and useDeferredValue keep the UI responsive during heavy updates
- React 19 adds Actions, useActionState, useOptimistic and the use hook
---
## Code splitting

By default all your code is in one bundle that every visitor downloads. Pages visitors may never open (an admin panel, a chart library) slow everyone down. **`lazy`** loads a component only when it is first rendered, and **`Suspense`** shows a fallback while it loads.

```jsx
import { lazy, Suspense } from "react";

const AdminPanel = lazy(() => import("./AdminPanel"));        // a separate file, downloaded on demand

function App({ isAdmin }) {
  return (
    <div>
      <h1>Dashboard</h1>
      {isAdmin && (
        <Suspense fallback={<p>Loading admin tools...</p>}>
          <AdminPanel />
        </Suspense>
      )}
    </div>
  );
}
```

The component you lazy-load must be a **default export**. Wrap lazy components in `Suspense` somewhere above them. The most common place to split is **per route**, so each page loads only its own code.

## Suspense for waiting

`Suspense` shows its `fallback` while anything inside is "waiting" for lazy code or for data from a Suspense-enabled library or framework. Place boundaries thoughtfully: one around the whole page gives a single big spinner, and several smaller ones let parts appear as they are ready.

```jsx
<Suspense fallback={<PageSkeleton />}>
  <Header />
  <Suspense fallback={<FeedSkeleton />}>
    <Feed />                       {/* slow part: the header can show first */}
  </Suspense>
</Suspense>
```

Suspense also works with the **`use`** hook (React 19), which reads a promise during render:

```jsx
import { use, Suspense } from "react";

function Comments({ commentsPromise }) {
  const comments = use(commentsPromise);       // waits here, so Suspense shows the fallback
  return <ul>{comments.map((c) => <li key={c.id}>{c.text}</li>)}</ul>;
}
```

Create the promise **outside** the component (in a parent, a router loader or a data library), so it is not recreated on every render.

## useTransition: keep typing smooth

Some updates are urgent (typing, clicking) and some can wait (filtering 10,000 rows). A **transition** marks an update as **not urgent**, so React keeps the input responsive and can interrupt the heavy work.

```jsx
import { useState, useTransition } from "react";

function SearchPage({ items }) {
  const [text, setText] = useState("");
  const [query, setQuery] = useState("");
  const [isPending, startTransition] = useTransition();

  function handleChange(e) {
    setText(e.target.value);                         // urgent: the input updates at once
    startTransition(() => setQuery(e.target.value)); // can wait: the heavy list updates when React has time
  }

  return (
    <>
      <input value={text} onChange={handleChange} />
      {isPending && <span>Updating...</span>}
      <BigList items={items} query={query} />
    </>
  );
}
```

`useDeferredValue` is a related tool for when you do not control the code that sets the value:

```jsx
const deferredQuery = useDeferredValue(query);       // lags behind during a slow render
return <BigList items={items} query={deferredQuery} />;
```

## What is new in React 19

| Feature | What it does |
| --- | --- |
| **Actions** | pass an async function to a form's `action`, and React tracks pending state and errors |
| **`useActionState`** | holds the result of an action (an error message, a success value) and a pending flag |
| **`useOptimistic`** | show the expected result immediately, and roll back if the request fails |
| **`use`** | read a promise or a context during render |
| **`ref` as a prop** | no more `forwardRef` for function components |
| **`<title>`, `<meta>` in components** | metadata can be rendered from any component |

```jsx
import { useActionState } from "react";

async function subscribe(previous, formData) {
  const email = formData.get("email");
  if (!email.includes("@")) return { error: "Enter a valid email." };
  await fetch("/api/subscribe", { method: "POST", body: JSON.stringify({ email }) });
  return { error: null, done: true };
}

function SubscribeForm() {
  const [result, formAction, isPending] = useActionState(subscribe, { error: null });
  return (
    <form action={formAction}>
      <input name="email" type="email" />
      <button disabled={isPending}>{isPending ? "Saving..." : "Subscribe"}</button>
      {result.error && <p role="alert">{result.error}</p>}
      {result.done && <p>Thanks!</p>}
    </form>
  );
}
```

```jsx
import { useOptimistic } from "react";

function LikeButton({ likes, sendLike }) {
  const [optimisticLikes, addOptimistic] = useOptimistic(likes, (current) => current + 1);

  async function handleClick() {
    addOptimistic();               // the count goes up instantly
    await sendLike();              // if this fails, React puts the real value back
  }
  return <button onClick={handleClick}>♥ {optimisticLikes}</button>;
}
```

## Server components, briefly

Frameworks such as **Next.js** let some components run **only on the server** (React Server Components). They can read a database directly and send **no JavaScript** to the browser for that part, which makes pages lighter. Interactive pieces stay as normal "client components". You do not need server components to build great React apps, but you will meet them in modern frameworks, so know the idea.

:::tip
Check which React version your project uses (`npm ls react`). Features such as `use`, `useActionState` and `useOptimistic` need React 19. `lazy`, `Suspense` and `useTransition` work from React 18.
:::
