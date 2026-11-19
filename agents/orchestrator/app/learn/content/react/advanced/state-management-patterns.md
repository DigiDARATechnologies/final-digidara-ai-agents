---
title: State management patterns
summary: Decide where each piece of state belongs: local, lifted, context, server cache or a store like Zustand.
takeaways:
- Most state should be local; share it only as far up as needed
- Server data is different from UI state: use a cache library such as TanStack Query
- Reach for a store only when context and lifting stop being comfortable
---
## Sort your state first

"State management" is not one problem. Separate the kinds of state, because each has a best home:

| Kind | Example | Best home |
| --- | --- | --- |
| **Local UI state** | is a menu open, text in a field | `useState` in the component |
| **Shared UI state** | selected tab used by two siblings | lift to the nearest common parent |
| **App-wide, rarely changing** | theme, current user, language | context |
| **Server state** | courses, orders, the profile from the API | TanStack Query or SWR |
| **URL state** | page number, filters, selected item | the URL (search params) |
| **Complex client state** | an editor, a multi-step wizard, a cart | `useReducer`, or a store (Zustand, Redux Toolkit) |
| **Form state** | values, errors, touched fields | React Hook Form, or local state |

Starting with the right category prevents most over-engineering.

## Server state is not UI state

Data from an API is a **cache of something that lives elsewhere**. It can go stale, needs loading and error states, retries, refetching and de-duplication. Writing that by hand in `useEffect` over and over is error-prone. **TanStack Query** handles it:

```jsx
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

function Courses() {
  const { data, isPending, error } = useQuery({
    queryKey: ["courses"],                       // the cache key
    queryFn: () => fetch("/api/courses").then((r) => r.json()),
    staleTime: 60_000,                           // fresh for one minute: no refetch on every mount
  });

  if (isPending) return <p>Loading...</p>;
  if (error) return <p>Failed to load.</p>;
  return <ul>{data.map((c) => <li key={c.id}>{c.title}</li>)}</ul>;
}

function AddCourse() {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (title) => fetch("/api/courses", { method: "POST", body: JSON.stringify({ title }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["courses"] }),   // refetch the list
  });
  return <button onClick={() => mutation.mutate("Flask")} disabled={mutation.isPending}>Add</button>;
}
```

You get caching, background refresh, retries, request de-duplication and shared data between components almost for free.

## A small store with Zustand

When state is shared widely and changes often, a small store is simpler than a stack of providers. Components subscribe to **just the slice they use**, so they re-render only when that slice changes:

```jsx
import { create } from "zustand";

const useCart = create((set, get) => ({
  items: [],
  add: (item) => set((s) => ({ items: [...s.items, item] })),
  clear: () => set({ items: [] }),
  total: () => get().items.reduce((sum, i) => sum + i.price, 0),
}));

function CartBadge() {
  const count = useCart((s) => s.items.length);       // re-renders only when the count changes
  return <span>Cart ({count})</span>;
}

function AddButton({ item }) {
  const add = useCart((s) => s.add);                   // never re-renders for item changes
  return <button onClick={() => add(item)}>Add</button>;
}
```

## Choosing

| Option | Good for | Cost |
| --- | --- | --- |
| `useState` + props | most things | passing props gets long in deep trees |
| context | theme, auth, i18n | all consumers re-render on any change |
| `useReducer` | complex local logic | more code than `useState` |
| TanStack Query / SWR | anything fetched | learning the query-key idea |
| Zustand / Jotai | shared client state with fine-grained updates | one more library |
| Redux Toolkit | very large apps, strict conventions, strong tooling | more boilerplate and concepts |

## Derived state: do not duplicate

If a value can be **calculated** from other state, do not store it:

```jsx
// Bad: two sources of truth that can drift apart
const [items, setItems] = useState([]);
const [count, setCount] = useState(0);          // must be kept in sync by hand

// Good: one source of truth
const [items, setItems] = useState([]);
const count = items.length;
```

:::tip
A good rule: keep state **as local as possible and as global as necessary**. Start local, lift when two components need it, and only then reach for context or a store. Most apps need far less global state than developers expect.
:::

:::interview
**Interviewers often ask:** "Redux, context or Zustand: how do you choose?" By the kind of state: context for rarely changing app-wide values, TanStack Query for server data, and a store (Zustand or Redux Toolkit) for large, frequently changing client state. Pick the lightest tool that fits.
:::
