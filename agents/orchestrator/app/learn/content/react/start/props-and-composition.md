---
title: Props and composition
summary: Pass data into components with props, set defaults, use children, and build bigger UIs by combining small components.
takeaways:
- Props are the inputs of a component; they are read-only
- children lets a component wrap other content
- Build UIs by composing small components rather than one giant one
---
## Props are inputs

A component becomes reusable when it takes **props** (short for properties), like a function takes arguments.

```jsx
function CourseCard({ title, lessons, level = "Beginner", free = false }) {
  return (
    <article className="card">
      <h3>{title}</h3>
      <p>{lessons} lessons · {level}</p>
      {free && <span className="badge">Free</span>}
    </article>
  );
}

export default function App() {
  return (
    <div>
      <CourseCard title="Python" lessons={15} free />
      <CourseCard title="React" lessons={19} level="Advanced" />
    </div>
  );
}
```

```output
<div>
<article class="card"><h3>Python</h3>
<p>15 lessons Â· Beginner</p>
<span class="badge">Free</span></article>
<article class="card"><h3>React</h3>
<p>19 lessons Â· Advanced</p>
</article>
</div>
```

Notice three things:

- Props arrive as one object, and we **destructure** it in the parameter list.
- `level = "Beginner"` is a **default value**, used when the prop is not passed.
- `free` with no value means `free={true}`. Strings go in quotes (`level="Advanced"`); everything else (numbers, booleans, objects, functions) goes in braces.

:::remember
Props are **read-only**. A component must never change its own props. If something needs to change over time, it belongs in **state**, which is the next lessons' topic.
:::

## children

Whatever you put between a component's opening and closing tags arrives as the special prop `children`:

```jsx
function Panel({ title, children }) {
  return (
    <section className="panel">
      <h3>{title}</h3>
      <div className="panel-body">{children}</div>
    </section>
  );
}

export default function App() {
  return (
    <Panel title="Today">
      <p>Two lessons to finish.</p>
      <button>Start</button>
    </Panel>
  );
}
```

```output
<section class="panel">
<h3>Today</h3>
<div class="panel-body">
<p>Two lessons to finish.</p>
<button>Start</button>
</div>
</section>
```

`Panel` does not need to know what is inside it. This is how layouts, cards, modals and page shells are built.

## Spreading props

```jsx
function Button({ variant = "primary", children, ...rest }) {
  return <button className={"btn btn-" + variant} {...rest}>{children}</button>;
}

export default function App() {
  return <Button variant="ghost" type="submit" disabled>Save</Button>;
}
```

```output
<button class="btn btn-ghost" type="submit" disabled="">Save</button>
```

`...rest` collects every prop you did not name, and `{...rest}` passes them on. The wrapper can add its own styling while `type` and `disabled` still reach the real `<button>`.

## Composition over giant components

Break a screen into small pieces that each do one thing:

```jsx
function Avatar({ name }) {
  return <span className="avatar">{name[0]}</span>;
}

function UserRow({ user }) {
  return (
    <li>
      <Avatar name={user.name} />
      <strong>{user.name}</strong> <small>{user.role}</small>
    </li>
  );
}

function UserList({ users }) {
  return <ul>{users.map((u) => <UserRow key={u.id} user={u} />)}</ul>;
}

export default function App() {
  const users = [
    { id: 1, name: "Asha", role: "Admin" },
    { id: 2, name: "Ravi", role: "Student" },
  ];
  return <UserList users={users} />;
}
```

```output
<ul>
<li><span class="avatar">A</span><strong>Asha</strong> <small>Admin</small></li>
<li><span class="avatar">R</span><strong>Ravi</strong> <small>Student</small></li>
</ul>
```

Each part is easy to read, test and reuse. If a component is longer than a screen, or you struggle to name it, it is probably doing too much.

:::tip
Data flows **down** the tree: parents pass props to children. To send information **up**, the parent passes a function as a prop and the child calls it. You will use this in the forms lesson.
:::
