---
title: Lists and conditional rendering
summary: Show data with map, choose what to display with conditions, and understand why keys matter.
takeaways:
- Use map to turn an array into elements, and give each item a stable key
- Show or hide parts with ternaries and &&, or return early
- Never use the array index as a key when items can be added, removed or reordered
---
## Rendering a list

```jsx
export default function App() {
  const courses = [
    { id: "py", title: "Python", lessons: 15 },
    { id: "sql", title: "SQL", lessons: 14 },
    { id: "react", title: "React", lessons: 19 },
  ];

  return (
    <ul>
      {courses.map((course) => (
        <li key={course.id}>
          {course.title} ({course.lessons} lessons)
        </li>
      ))}
    </ul>
  );
}
```

```output
<ul>
<li>Python (15 lessons)</li>
<li>SQL (14 lessons)</li>
<li>React (19 lessons)</li>
</ul>
```

`map` turns each data item into an element. The **`key`** prop is required: it gives each item a stable identity.

## Why keys matter

When the list changes, React compares old and new items **by key** to find what moved, was added or was removed. Without a good key, React can attach the wrong state to the wrong item.

| Key choice | Verdict |
| --- | --- |
| a database id or slug | best: unique and stable |
| the array index | only OK for static lists that never reorder |
| `Math.random()` | bad: a new key every render, so everything is recreated |

:::warning
With index keys, deleting the first item makes every other item shift keys. A typed-in value or a checked box can then appear on the wrong row. Use a real id.
:::

Keys need to be unique only **among siblings**, and they are not passed as a prop (your component cannot read `props.key`).

## Filtering and sorting

Derive what to show from the original data. Do not store the filtered copy in state:

```jsx
export default function App() {
  const students = [
    { id: 1, name: "Asha", marks: 92 },
    { id: 2, name: "Ravi", marks: 48 },
    { id: 3, name: "Meena", marks: 85 },
  ];
  const passed = students.filter((s) => s.marks >= 50).sort((a, b) => b.marks - a.marks);

  return (
    <div>
      <p>{passed.length} of {students.length} passed</p>
      <ol>{passed.map((s) => <li key={s.id}>{s.name}: {s.marks}</li>)}</ol>
    </div>
  );
}
```

```output
<div>
<p>2 of 3 passed</p>
<ol>
<li>Asha: 92</li>
<li>Meena: 85</li>
</ol>
</div>
```

## Conditional rendering

```jsx
function Notice({ unread, loggedIn }) {
  if (!loggedIn) return <p>Please sign in.</p>;            // return early

  return (
    <div>
      <h3>Inbox {unread > 0 ? `(${unread})` : "(empty)"}</h3>       {/* ternary: A or B */}
      {unread > 0 && <button>Mark all read</button>}                  {/* && : A or nothing */}
    </div>
  );
}

export default function App() {
  return (
    <div>
      <Notice loggedIn={false} unread={0} />
      <Notice loggedIn unread={3} />
      <Notice loggedIn unread={0} />
    </div>
  );
}
```

```output
<div>
<p>Please sign in.</p>
<div>
<h3>Inbox (3)</h3>       <button>Mark all read</button>                  </div>
<div>
<h3>Inbox (empty)</h3>                         </div>
</div>
```

| Pattern | Use for |
| --- | --- |
| early `return` | a whole different output (loading, error, empty) |
| `cond ? <A /> : <B />` | pick one of two |
| `cond && <A />` | show something or nothing |

:::warning
With `&&`, a left side of `0` renders the **number 0**. Write `{items.length > 0 && <List />}`, not `{items.length && <List />}`.
:::

## The three states of data

Almost every list screen has the same cases. Handle them all:

```jsx
function Results({ status, items }) {
  if (status === "loading") return <p>Loading...</p>;
  if (status === "error") return <p role="alert">Could not load. Try again.</p>;
  if (items.length === 0) return <p>Nothing here yet.</p>;
  return <ul>{items.map((i) => <li key={i}>{i}</li>)}</ul>;
}

export default function App() {
  return (
    <div>
      <Results status="loading" items={[]} />
      <Results status="error" items={[]} />
      <Results status="done" items={[]} />
      <Results status="done" items={["Python", "SQL"]} />
    </div>
  );
}
```

```output
<div>
<p>Loading...</p>
<p role="alert">Could not load. Try again.</p>
<p>Nothing here yet.</p>
<ul>
<li>Python</li>
<li>SQL</li>
</ul>
</div>
```

A polished app never shows a blank screen: loading, error and empty states each get their own message.
